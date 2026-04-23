from datetime import timedelta
import os
import textwrap

import boto3
from django.utils import timezone
from reportlab.graphics import renderPDF
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from ..models import CaseRun, Issue, Page, Scan, Site, Test
from cursion import settings


class Reporter:
    """
    Generates a site-level PDF report for the associated `Report` object.

    Returns:
        'report' : object,
        'success': bool,
        'message': str
    """

    VALID_LOOKBACK_DAYS = {1, 7, 30, 90}
    VALID_TYPES         = {"issues", "tests", "caseruns", "performance"}
    FONT_REGULAR        = "Helvetica"
    FONT_BOLD           = "Helvetica-Bold"

    def __init__(self, report: object, scan: object = None):
        self.report = report
        self.scan = scan
        self.site = self.report.site

        if self.site is None and self.report.page is not None:
            self.site = self.report.page.site

        info = self.report.info if isinstance(self.report.info, dict) else {}
        self.text_color = info.get("text_color", "#24262d")
        self.highlight_color = info.get("highlight_color", "#ffffff")
        self.background_color = info.get("background_color", "#e1effd")

        reports_dir = os.path.join(settings.BASE_DIR, "reports")
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
        self.local_path = os.path.join(reports_dir, f"{self.report.id}.pdf")

        self.page_index = 0
        self.c = canvas.Canvas(self.local_path, letter)

        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=str(settings.AWS_ACCESS_KEY_ID),
            aws_secret_access_key=str(settings.AWS_SECRET_ACCESS_KEY),
            region_name=str(settings.AWS_S3_REGION_NAME),
            endpoint_url=str(settings.AWS_S3_ENDPOINT_URL),
        )


    def _with_alpha(self, color_hex: str, alpha_hex: str) -> HexColor:
        color_hex = str(color_hex or "#000000").strip()
        if not color_hex.startswith("#"):
            color_hex = f"#{color_hex}"
        if len(color_hex) != 7:
            color_hex = "#000000"
        return HexColor(f"{color_hex}{alpha_hex}", hasAlpha=True)


    def _fit_text(self, text: str, font_name: str, font_size: float, max_width_px: float) -> str:
        value = str(text or "")
        if self.c.stringWidth(value, font_name, font_size) <= max_width_px:
            return value

        suffix = "..."
        low = 0
        high = len(value)
        best = ""
        while low <= high:
            mid = (low + high) // 2
            candidate = f"{value[:mid]}{suffix}"
            if self.c.stringWidth(candidate, font_name, font_size) <= max_width_px:
                best = candidate
                low = mid + 1
            else:
                high = mid - 1
        return best or suffix


    def _wrap_text_to_width(self, text: str, font_name: str, font_size: float, max_width_px: float) -> list[str]:
        value = str(text or "").replace("\n", " ").strip()
        if not value:
            return [""]

        words = value.split()
        lines: list[str] = []
        current = ""

        for word in words:
            candidate = f"{current} {word}".strip()
            if current and self.c.stringWidth(candidate, font_name, font_size) > max_width_px:
                lines.append(current)
                current = word
                if self.c.stringWidth(current, font_name, font_size) > max_width_px:
                    chunk = ""
                    for char in current:
                        next_chunk = f"{chunk}{char}"
                        if chunk and self.c.stringWidth(next_chunk, font_name, font_size) > max_width_px:
                            lines.append(chunk)
                            chunk = char
                        else:
                            chunk = next_chunk
                    current = chunk
            else:
                current = candidate

        if current:
            lines.append(current)

        return lines or [""]


    def setup_page(self) -> None:
        self.c.setFillColor(HexColor(self.background_color))
        self.c.rect(0, 0, 8.5 * inch, 11 * inch, stroke=0, fill=1)


    def end_page(self) -> None:
        self.c.setFont(self.FONT_BOLD, 10)
        self.c.setFillColor(HexColor(self.text_color))
        self.page_index += 1
        self.c.drawString(7.7 * inch, 0.3 * inch, str(self.page_index))
        self.c.showPage()


    def draw_page_title(self, title: str, subtitle: str | None = None) -> None:
        self.c.setFont(self.FONT_BOLD, 27)
        self.c.setFillColor(HexColor(self.text_color))
        self.c.drawString(0.5 * inch, 9.9 * inch, title)
        if subtitle:
            self.c.setFont(self.FONT_REGULAR, 11)
            self.c.drawString(0.5 * inch, 9.56 * inch, subtitle)


    def draw_wrapped_line(self, text: str, length: int, x_pos: float, y_pos: float, y_offset: float) -> float:
        wraps = textwrap.wrap(str(text), length, break_long_words=True) or [""]
        for line in wraps:
            self.c.drawString(x_pos * inch, y_pos * inch, line)
            y_pos -= y_offset
        return y_pos


    def _draw_stat_card(self, x: float, y: float, w: float, h: float, title: str, value: str, subtitle: str = "", value_font_size: float = 17) -> None:
        self.c.setFillColor(self._with_alpha(self.highlight_color, "CF"))
        self.c.roundRect(x * inch, y * inch, w * inch, h * inch, 0.1 * inch, stroke=0, fill=1)

        self.c.setFillColor(HexColor(self.text_color))
        self.c.setFont(self.FONT_REGULAR, 9)
        self.c.drawString((x + 0.14) * inch, (y + h - 0.22) * inch, title)

        fitted_value = self._fit_text(value, self.FONT_BOLD, value_font_size, (w - 0.28) * inch)
        self.c.setFont(self.FONT_BOLD, value_font_size)
        self.c.drawString((x + 0.14) * inch, (y + 0.34) * inch, fitted_value)

        if subtitle:
            self.c.setFont(self.FONT_REGULAR, 8)
            self.c.drawString((x + 0.14) * inch, (y + 0.13) * inch, self._fit_text(subtitle, self.FONT_REGULAR, 8, (w - 0.28) * inch))


    def _draw_pie_chart(self, x: float, y: float, w: float, h: float, title: str, data_pairs: list[tuple[str, float]]) -> None:
        values = [float(max(0, p[1])) for p in data_pairs]
        labels = [str(p[0]) for p in data_pairs]
        if not values or sum(values) <= 0:
            self.c.setFont(self.FONT_REGULAR, 10)
            self.c.setFillColor(HexColor(self.text_color))
            self.c.drawString(x * inch, y * inch, f"{title}: no data")
            return

        drawing = Drawing(w * inch, h * inch)
        pie = Pie()
        pie_bottom = 0.08 * inch
        pie_top = (h * inch) - 0.55 * inch
        max_pie_width = (w - 0.2) * inch
        max_pie_height = max(0.6 * inch, pie_top - pie_bottom)
        pie_size = min(max_pie_width, max_pie_height)
        pie.x = ((w * inch) - pie_size) / 2
        pie.y = pie_bottom + ((max_pie_height - pie_size) / 2)
        pie.width = pie_size
        pie.height = pie_size
        pie.data = values
        pie.labels = labels
        pie.slices.strokeWidth = 0.5
        pie.slices.fontName = self.FONT_REGULAR
        pie.slices.fontSize = 8

        palette = [
            HexColor("#38B43F"),
            HexColor("#DB524B"),
            HexColor("#E3A635"),
            HexColor("#4B79DB"),
            HexColor("#9A5FDB"),
            HexColor("#4DB2A7"),
        ]
        for i in range(len(values)):
            pie.slices[i].fillColor = palette[i % len(palette)]

        drawing.add(pie)
        drawing.add(String(4, h * inch - 12, title, fontName=self.FONT_BOLD, fontSize=10, fillColor=HexColor(self.text_color)))
        renderPDF.draw(drawing, self.c, x * inch, y * inch)


    def _draw_bar_chart(self, x: float, y: float, w: float, h: float, title: str, labels: list[str], values: list[float]) -> None:
        if not values:
            self.c.setFont(self.FONT_REGULAR, 10)
            self.c.setFillColor(HexColor(self.text_color))
            self.c.drawString(x * inch, y * inch, f"{title}: no data")
            return

        data_max = max(float(v) for v in values)
        if data_max <= 0:
            axis_max = 1.0
        elif data_max <= 5:
            axis_max = data_max + 1
        else:
            axis_max = data_max * 1.1
        axis_step = max(1.0, round(axis_max / 5))

        chart_w_px = w * inch
        chart_h_px = h * inch
        title_y = chart_h_px - 12

        indexed_labels = [str(i + 1) for i in range(len(labels))]
        legend_font_size = 7
        legend_line_h = 0.1 * inch
        legend_item_gap = 0.03 * inch
        legend_top_margin = 0.18 * inch
        legend_bottom_gap = 0.1 * inch
        legend_cols = 1 if len(labels) <= 3 else 2
        legend_gap = 0.16 * inch if legend_cols > 1 else 0
        legend_width = chart_w_px - 0.16 * inch
        legend_col_width = max(1.0 * inch, (legend_width - legend_gap) / legend_cols)

        col_split = max(1, (len(labels) + legend_cols - 1) // legend_cols)
        legend_entries: list[list[tuple[int, list[str]]]] = [[] for _ in range(legend_cols)]
        col_heights = [0.0 for _ in range(legend_cols)]

        for i, label in enumerate(labels):
            col = min(i // col_split, legend_cols - 1)
            wrapped = self._wrap_text_to_width(f"{i + 1}: {label}", self.FONT_REGULAR, legend_font_size, legend_col_width)
            legend_entries[col].append((i + 1, wrapped))
            col_heights[col] += (len(wrapped) * legend_line_h) + legend_item_gap

        legend_height = max(col_heights) if legend_entries else 0
        chart_top = title_y - legend_top_margin - legend_height - legend_bottom_gap
        chart_y = 0.4 * inch
        chart_height = max(0.95 * inch, chart_top - chart_y)

        drawing = Drawing(w * inch, h * inch)
        chart = VerticalBarChart()
        chart.x = 0.45 * inch
        chart.y = chart_y
        chart.width = (w - 0.7) * inch
        chart.height = chart_height
        chart.data = [values]
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = axis_max
        chart.valueAxis.valueStep = axis_step
        chart.valueAxis.labels.fontSize = 7
        chart.valueAxis.labels.fontName = self.FONT_REGULAR
        chart.categoryAxis.categoryNames = indexed_labels
        chart.categoryAxis.labels.fontSize = 7
        chart.categoryAxis.labels.fontName = self.FONT_REGULAR
        chart.categoryAxis.labels.boxAnchor = "n"
        chart.barWidth = 0.17 * inch
        chart.groupSpacing = 0.14 * inch
        chart.barSpacing = 0.05 * inch
        chart.bars[0].fillColor = self._with_alpha(self.highlight_color, "E6")
        chart.strokeColor = self._with_alpha(self.text_color, "66")

        drawing.add(chart)
        drawing.add(String(4, title_y, title, fontName=self.FONT_BOLD, fontSize=10, fillColor=HexColor(self.text_color)))

        legend_y_start = title_y - legend_top_margin
        for col, entries in enumerate(legend_entries):
            lx = (0.08 * inch) + (col * (legend_col_width + legend_gap))
            ly = legend_y_start
            for _, wrapped in entries:
                for line in wrapped:
                    drawing.add(String(lx, ly, line, fontName=self.FONT_REGULAR, fontSize=legend_font_size, fillColor=HexColor(self.text_color)))
                    ly -= legend_line_h
                ly -= legend_item_gap

        renderPDF.draw(drawing, self.c, x * inch, y * inch)


    def _draw_design_list(self, x: float, y: float, w: float, row_h: float, title: str, items: list[dict], max_rows: int = 6) -> None:
        self.c.setFont(self.FONT_BOLD, 10)
        self.c.setFillColor(HexColor(self.text_color))
        self.c.drawString(x * inch, y * inch, title)
        self.c.setStrokeColor(self._with_alpha(self.text_color, "44"))
        self.c.line(x * inch, (y - 0.04) * inch, (x + w) * inch, (y - 0.04) * inch)

        y -= 0.15
        cursor_y = y
        for idx, item in enumerate(items[:max_rows], start=1):
            accent_color = item.get("accent_color", "#4B79DB")
            badge = item.get("badge")
            badge_w = 0
            if badge:
                badge_w = min(2.1, 0.28 + (len(str(badge)) * 0.065))

            left_padding = 0.11 * inch
            right_padding = 0.1 * inch
            max_text_width = max(28, (w * inch) - left_padding - right_padding - ((badge_w + 0.18) * inch if badge else 0))

            headline_font_size = 8.7
            meta_font_size = 8
            headline_line_h = 0.125 * inch
            meta_line_h = 0.118 * inch
            headline_meta_gap = 0.102 * inch
            top_bottom_padding = 0.085 * inch

            headline_lines = self._wrap_text_to_width(item.get("headline", ""), self.FONT_BOLD, headline_font_size, max_text_width)
            meta_lines = self._wrap_text_to_width(item.get("meta", ""), self.FONT_REGULAR, meta_font_size, max_text_width)
            headline_block_h = max(0, (len(headline_lines) - 1)) * headline_line_h
            meta_block_h = max(0, (len(meta_lines) - 1)) * meta_line_h
            content_h = headline_block_h + headline_meta_gap + meta_block_h
            box_h = max((row_h - 0.04) * inch, content_h + (top_bottom_padding * 2))
            box_h_in = box_h / inch
            box_y = cursor_y - box_h_in
            box_y_px = box_y * inch

            alpha = "A8" if idx % 2 else "8F"
            self.c.setFillColor(self._with_alpha(self.highlight_color, alpha))
            self.c.roundRect(x * inch, box_y_px, w * inch, box_h, 0.05 * inch, stroke=0, fill=1)

            self.c.setFillColor(self._with_alpha(accent_color, "EE"))
            self.c.roundRect(x * inch, box_y_px, 0.06 * inch, box_h, 0.03 * inch, stroke=0, fill=1)

            if badge:
                badge_x = x + w - badge_w - 0.1
                badge_color = item.get("badge_color", "#4B79DB")
                self.c.setFillColor(self._with_alpha(badge_color, "DD"))
                badge_h = 0.18 * inch
                badge_y = box_y_px + ((box_h - badge_h) / 2)
                self.c.roundRect(badge_x * inch, badge_y, badge_w * inch, badge_h, 0.08 * inch, stroke=0, fill=1)
                self.c.setFillColor(HexColor("#ffffff"))
                self.c.setFont(self.FONT_BOLD, 7.3)
                self.c.drawCentredString((badge_x + (badge_w / 2)) * inch, badge_y + (0.055 * inch), str(badge))

            text_x = (x + 0.11) * inch
            line_y = box_y_px + (box_h / 2) + (content_h / 2)

            self.c.setFillColor(HexColor(self.text_color))
            self.c.setFont(self.FONT_BOLD, headline_font_size)
            for i, line in enumerate(headline_lines):
                self.c.drawString(text_x, line_y, line)
                if i < len(headline_lines) - 1:
                    line_y -= headline_line_h

            line_y -= headline_meta_gap
            self.c.setFont(self.FONT_REGULAR, meta_font_size)
            for i, line in enumerate(meta_lines):
                self.c.drawString(text_x, line_y, line)
                if i < len(meta_lines) - 1:
                    line_y -= meta_line_h

            cursor_y = box_y - 0.04


    def _normalize_types(self):
        raw_types = self.report.type
        if raw_types is None:
            info = self.report.info if isinstance(self.report.info, dict) else {}
            raw_types = info.get("types") or info.get("type")

        if isinstance(raw_types, str):
            selected = [raw_types]
        elif isinstance(raw_types, list):
            selected = [item for item in raw_types if isinstance(item, str)]
        else:
            selected = []

        selected = list(dict.fromkeys([item.strip().lower() for item in selected if item.strip()]))

        if not selected:
            return None, "Invalid report config: `type` is required and must be a non-empty array."

        invalid = [item for item in selected if item not in self.VALID_TYPES]
        if invalid:
            return None, f"Invalid report config: unsupported `type` values {invalid}. Supported values: {sorted(self.VALID_TYPES)}."

        return selected, None


    def _get_lookback_days(self):
        info = self.report.info if isinstance(self.report.info, dict) else {}
        raw_days = info.get("lookback_days")
        try:
            lookback_days = int(raw_days)
        except Exception:
            return None, "Invalid report config: `lookback_days` is required (1, 7, 30, or 90)."

        if lookback_days not in self.VALID_LOOKBACK_DAYS:
            return None, "Invalid report config: `lookback_days` must be one of 1, 7, 30, 90."

        return lookback_days, None


    def _resolve_site(self):
        if self.site is not None:
            return self.site, None

        info = self.report.info if isinstance(self.report.info, dict) else {}
        site_id = info.get("site_id")
        if not site_id:
            return None, "Report generation failed: `site_id` is required for site-level reports."

        try:
            site = Site.objects.get(id=site_id)
        except Site.DoesNotExist:
            return None, f"Report generation failed: site `{site_id}` not found."

        self.site = site
        self.report.site = site
        return site, None


    def _build_issues_data(self, window_start, now):
        records = []
        _ids = [str(p.id) for p in Page.objects.filter(site=self.site)] + [str(self.site.id)]
        issues = (
            Issue.objects.filter(account=self.report.account, status="open", time_created__gte=window_start, affected__id__in=_ids)
            .order_by("-time_created")
        )

        print('SCRAPPED ISSUES')
        print(issues)

        for issue in issues:
            affected = issue.affected if isinstance(issue.affected, dict) else {}
            if str(affected.get("id") or "") not in _ids:
                continue
            created = issue.time_created
            age_days = max((now - created).days, 0) if created else None
            records.append(
                {
                    "title": issue.title or "Untitled issue",
                    "affected": affected.get("str"),
                    "created": created,
                    "age_days": age_days,
                }
            )

        return {"count": len(records), "records": records}


    def _build_tests_data(self, window_start):
        tests_qs = (
            Test.objects.filter(site=self.site, time_completed__isnull=False, time_completed__gte=window_start)
            .select_related("page")
            .order_by("page_id", "-time_completed")
        )

        total_tests, pass_count, fail_count, incomplete_count = 0, 0, 0, 0
        score_total, score_count = 0.0, 0
        latest_by_page = {}

        for test in tests_qs:
            total_tests += 1
            status_raw = (test.status or "").strip().lower()
            if status_raw.startswith("pass"):
                pass_count += 1
            elif status_raw.startswith("fail"):
                fail_count += 1
            else:
                incomplete_count += 1

            if test.score is not None:
                score_total += float(test.score)
                score_count += 1

            page_key = str(test.page_id) if test.page_id else f"__missing_{test.id}"
            if page_key in latest_by_page:
                continue
            latest_by_page[page_key] = {
                "page_url": test.page.page_url if test.page else "Unknown page",
                "score": test.score,
                "status": test.status or "unknown",
                "time_completed": test.time_completed,
            }

        return {
            "rollup": {
                "total_tests": total_tests,
                "pass_count": pass_count,
                "fail_count": fail_count,
                "incomplete_count": incomplete_count,
                "avg_score": round(score_total / score_count, 2) if score_count else None,
            },
            "pages": sorted(latest_by_page.values(), key=lambda x: (x["page_url"] or "")),
        }


    def _build_caseruns_data(self, window_start):
        qs = CaseRun.objects.filter(site=self.site, time_created__gte=window_start).order_by("-time_created")
        status_counts, latest_runs = {}, []
        for run in qs:
            status_key = (run.status or "unknown").strip().lower() or "unknown"
            status_counts[status_key] = status_counts.get(status_key, 0) + 1
            if len(latest_runs) < 10:
                latest_runs.append({"title": run.title or "Untitled run", "status": run.status or "unknown", "time_created": run.time_created})
        return {"count": qs.count(), "status_counts": status_counts, "latest_runs": latest_runs}


    def _build_performance_data(self, window_start):
        scans_qs = (
            Scan.objects.filter(site=self.site, time_completed__isnull=False, time_completed__gte=window_start)
            .select_related("page")
            .order_by("page_id", "-time_completed")
        )

        latest_by_page, scores = {}, []
        for scan in scans_qs:
            page_key = str(scan.page_id) if scan.page_id else f"__missing_{scan.id}"
            if page_key in latest_by_page:
                continue
            if scan.score is not None:
                scores.append(float(scan.score))
            latest_by_page[page_key] = {"page_url": scan.page.page_url if scan.page else "Unknown page", "health": scan.score, "time_completed": scan.time_completed}

        return {
            "pages": sorted(latest_by_page.values(), key=lambda x: (x["page_url"] or "")),
            "rollup": {
                "avg_health": round(sum(scores) / len(scores), 2) if scores else None,
                "min_health": round(min(scores), 2) if scores else None,
                "max_health": round(max(scores), 2) if scores else None,
                "pages_with_data": len(scores),
            },
        }


    def _build_datasets(self, selected_types, lookback_days):
        now = timezone.now()
        window_start = now - timedelta(days=lookback_days)
        pages = list(Page.objects.filter(site=self.site).order_by("page_url"))

        datasets = {}
        if "issues" in selected_types:
            datasets["issues"] = self._build_issues_data(window_start=window_start, now=now)
        if "tests" in selected_types:
            datasets["tests"] = self._build_tests_data(window_start=window_start)
        if "caseruns" in selected_types:
            datasets["caseruns"] = self._build_caseruns_data(window_start=window_start)
        if "performance" in selected_types:
            datasets["performance"] = self._build_performance_data(window_start=window_start)

        return {
            "generated_at": now,
            "window_start": window_start,
            "site": {"id": str(self.site.id), "site_url": self.site.site_url, "total_pages": len(pages)},
            "datasets": datasets,
        }


    def _safe_score(self, value):
        if value is None:
            return "n/a"
        try:
            return f"{float(value):.2f}"
        except Exception:
            return str(value)


    def _render_cover_page(self, selected_types, lookback_days, snapshot):
        self.setup_page()
        now = snapshot["generated_at"]
        window_start = snapshot["window_start"]
        date_range = f"{window_start.strftime('%b %d, %Y')} - {now.strftime('%b %d, %Y')}"

        self.c.setFillColor(HexColor(self.text_color))
        self.c.setFont(self.FONT_BOLD, 40)
        self.c.drawString(0.5 * inch, 9.65 * inch, "Site Report")

        self.c.setFont(self.FONT_BOLD, 18)
        self.draw_wrapped_line(text=self.site.site_url or f"Site {self.site.id}", length=58, x_pos=0.5, y_pos=9.15, y_offset=0.3)

        self.c.setFont(self.FONT_REGULAR, 10)
        # self.c.drawString(0.5 * inch, 8.3 * inch, f"Generated: {now.strftime('%Y-%m-%d %H:%M %Z')}")
        # self.c.drawString(0.5 * inch, 8.1 * inch, f"Report range: {date_range}")
        # self.c.drawString(0.5 * inch, 7.9 * inch, f"Sections: {', '.join(selected_types)}")

        self._draw_stat_card(0.5, 6.9, 2.35, 1.0, "Site Pages", str(snapshot["site"]["total_pages"]))
        self._draw_stat_card(3.0, 6.9, 2.0, 1.0, "Sections", str(len(selected_types)))
        self._draw_stat_card(5.15, 6.9, 2.85, 1.0, "Date Range", date_range, value_font_size=9)

        section_items = [{"headline": s.title(), "meta": f"Included in this export ({lookback_days}d window)", "badge": "enabled", "badge_color": "#38B43F", "accent_color": "#4B79DB"} for s in selected_types]
        self._draw_design_list(0.5, 6.5, 7.5, 0.5, "Included sections", section_items, max_rows=8)
        self.end_page()


    def _render_issues_section(self, data):
        self.setup_page()
        self.draw_page_title("Issues", "Open issues created in the selected lookback window")

        records = data.get("records", [])
        ages = [int(item.get("age_days") or 0) for item in records]
        avg_age = round(sum(ages) / len(ages), 1) if ages else 0
        max_age = max(ages) if ages else 0

        buckets = {"0-1d": 0, "2-7d": 0, "8-30d": 0, "30+d": 0}
        for age in ages:
            if age <= 1:
                buckets["0-1d"] += 1
            elif age <= 7:
                buckets["2-7d"] += 1
            elif age <= 30:
                buckets["8-30d"] += 1
            else:
                buckets["30+d"] += 1

        self._draw_stat_card(0.5, 8.25, 2.45, 1.0, "Open Issues", str(data.get("count", 0)))
        self._draw_stat_card(3.1, 8.25, 2.45, 1.0, "Avg Age", f"{avg_age}d")
        self._draw_stat_card(5.7, 8.25, 2.3, 1.0, "Oldest", f"{max_age}d")

        self._draw_bar_chart(0.5, 5.25, 3.9, 2.7, "Issue age buckets", list(buckets.keys()), [float(v) for v in buckets.values()])

        items = []
        for issue in records[:8]:
            created_str = issue["created"].strftime("%Y-%m-%d") if issue.get("created") else "n/a"
            age_days = int(issue.get("age_days", 0) or 0)
            badge_color = "#38B43F" if age_days <= 1 else ("#E3A635" if age_days <= 7 else "#DB524B")
            items.append({"headline": issue.get("title", "Untitled issue"), "meta": f"affected: {issue.get('affected', 'site')} | created: {created_str}", "badge": f"{age_days}d", "badge_color": badge_color, "accent_color": badge_color})

        if not items:
            items = [{"headline": "No open site issues were created during this lookback window.", "meta": "Everything in the selected window looks clean.", "badge": "ok", "badge_color": "#38B43F", "accent_color": "#38B43F"}]

        self._draw_design_list(4.55, 7.95, 3.45, 0.5, "Recent open issues", items, max_rows=8)
        self.end_page()


    def _render_tests_section(self, data):
        self.setup_page()
        self.draw_page_title("Tests", "Latest completed tests per page with site-level status mix")

        rollup = data.get("rollup", {})
        pages = data.get("pages", [])

        self._draw_stat_card(0.5, 8.25, 1.85, 1.0, "Total", str(rollup.get("total_tests", 0)))
        self._draw_stat_card(2.45, 8.25, 1.85, 1.0, "Pass", str(rollup.get("pass_count", 0)))
        self._draw_stat_card(4.4, 8.25, 1.85, 1.0, "Fail", str(rollup.get("fail_count", 0)))
        self._draw_stat_card(6.35, 8.25, 1.65, 1.0, "Avg Score", self._safe_score(rollup.get("avg_score")))

        self._draw_pie_chart(0.5, 5.15, 3.9, 2.9, "Status distribution", [("pass", rollup.get("pass_count", 0)), ("fail", rollup.get("fail_count", 0)), ("incomplete", rollup.get("incomplete_count", 0))])

        score_rows = [item for item in pages if item.get("score") is not None][:8]
        labels = [item.get("page_url", "page") for item in score_rows]
        values = [float(item.get("score") or 0) for item in score_rows]
        self._draw_bar_chart(4.55, 5.15, 3.45, 2.9, "Per-page latest score", labels, values)

        items = []
        for item in pages[:7]:
            completed = item["time_completed"].strftime("%Y-%m-%d") if item.get("time_completed") else "n/a"
            status_label = str(item.get("status", "unknown")).lower()
            badge_color = "#38B43F" if status_label.startswith("pass") else ("#DB524B" if status_label.startswith("fail") else "#E3A635")
            items.append({"headline": item.get("page_url", "Unknown page"), "meta": f"score: {self._safe_score(item.get('score'))} | completed: {completed}", "badge": item.get("status", "unknown"), "badge_color": badge_color, "accent_color": badge_color})

        if not items:
            items = [{"headline": "No completed tests found in this lookback window.", "meta": "Run tests to populate this section.", "badge": "none", "badge_color": "#4B79DB", "accent_color": "#4B79DB"}]

        self._draw_design_list(0.5, 4.8, 7.5, 0.5, "Per-page latest completed tests", items, max_rows=7)
        self.end_page()


    def _render_caseruns_section(self, data):
        self.setup_page()
        self.draw_page_title("Case Runs", "Case run activity and status distribution in lookback window")

        status_counts = data.get("status_counts", {})
        latest_runs = data.get("latest_runs", [])

        self._draw_stat_card(0.5, 8.25, 2.45, 1.0, "Total Runs", str(data.get("count", 0)))
        self._draw_stat_card(3.1, 8.25, 2.45, 1.0, "Statuses", str(len(status_counts.keys())))
        self._draw_stat_card(5.7, 8.25, 2.3, 1.0, "Latest Rows", str(len(latest_runs)))

        ordered_statuses = sorted(status_counts.items(), key=lambda i: i[1], reverse=True)
        self._draw_pie_chart(0.5, 5.2, 3.9, 2.8, "Run statuses", [(k, v) for k, v in ordered_statuses])

        labels = [item[0] for item in ordered_statuses[:8]]
        values = [float(item[1]) for item in ordered_statuses[:8]]
        self._draw_bar_chart(4.55, 5.2, 3.45, 2.8, "Status counts", labels, values)

        items = []
        for run in latest_runs[:7]:
            created = run["time_created"].strftime("%Y-%m-%d %H:%M") if run.get("time_created") else "n/a"
            status_label = str(run.get("status", "unknown")).lower()
            badge_color = "#38B43F" if status_label in ["passed", "pass", "success", "complete"] else ("#DB524B" if status_label in ["failed", "fail", "error"] else "#E3A635")
            items.append({"headline": run.get("title", "Untitled run"), "meta": f"created: {created}", "badge": run.get("status", "unknown"), "badge_color": badge_color, "accent_color": badge_color})

        if not items:
            items = [{"headline": "No case runs found in this lookback window.", "meta": "Run a case to populate this section.", "badge": "none", "badge_color": "#4B79DB", "accent_color": "#4B79DB"}]

        self._draw_design_list(0.5, 4.8, 7.5, 0.5, "Latest runs", items, max_rows=7)
        self.end_page()


    def _render_performance_section(self, data):
        self.setup_page()
        self.draw_page_title("Performance", "Latest completed scan health scores per page")

        rollup = data.get("rollup", {})
        pages = data.get("pages", [])

        self._draw_stat_card(0.5, 8.25, 1.85, 1.0, "Pages", str(rollup.get("pages_with_data", 0)))
        self._draw_stat_card(2.45, 8.25, 1.85, 1.0, "Avg", self._safe_score(rollup.get("avg_health")))
        self._draw_stat_card(4.4, 8.25, 1.85, 1.0, "Min", self._safe_score(rollup.get("min_health")))
        self._draw_stat_card(6.35, 8.25, 1.65, 1.0, "Max", self._safe_score(rollup.get("max_health")))

        scored_pages = [item for item in pages if item.get("health") is not None]
        labels = [item.get("page_url", "page") for item in scored_pages[:10]]
        values = [float(item.get("health") or 0) for item in scored_pages[:10]]
        self._draw_bar_chart(0.5, 5.2, 7.5, 2.8, "Latest page health scores", labels, values)

        lowest = sorted(scored_pages, key=lambda x: float(x.get("health") or 0))[:7]
        items = []
        for item in lowest:
            completed = item["time_completed"].strftime("%Y-%m-%d") if item.get("time_completed") else "n/a"
            score = float(item.get("health") or 0)
            badge_color = "#38B43F" if score >= 80 else ("#E3A635" if score >= 50 else "#DB524B")
            items.append({"headline": item.get("page_url", "Unknown page"), "meta": f"completed: {completed}", "badge": self._safe_score(item.get("health")), "badge_color": badge_color, "accent_color": badge_color})

        if not items:
            items = [{"headline": "No completed scans found in this lookback window.", "meta": "Run scans to populate performance health rows.", "badge": "none", "badge_color": "#4B79DB", "accent_color": "#4B79DB"}]

        self._draw_design_list(0.5, 4.8, 7.5, 0.5, "Lowest health pages (attention)", items, max_rows=7)
        self.end_page()


    def _render_sections(self, selected_types, snapshot):
        datasets = snapshot["datasets"]
        for section_type in selected_types:
            if section_type == "issues":
                self._render_issues_section(datasets.get("issues", {"count": 0, "records": []}))
            elif section_type == "tests":
                self._render_tests_section(datasets.get("tests", {"rollup": {"total_tests": 0, "pass_count": 0, "fail_count": 0, "incomplete_count": 0, "avg_score": None}, "pages": []}))
            elif section_type == "caseruns":
                self._render_caseruns_section(datasets.get("caseruns", {"count": 0, "status_counts": {}, "latest_runs": []}))
            elif section_type == "performance":
                self._render_performance_section(datasets.get("performance", {"rollup": {"avg_health": None, "min_health": None, "max_health": None, "pages_with_data": 0}, "pages": []}))


    def publish_report(self) -> None:
        self.c.save()
        remote_path = f"static/sites/{self.site.id}/reports/{self.report.id}.pdf"

        with open(self.local_path, "rb") as data:
            self.s3.upload_fileobj(
                data,
                str(settings.AWS_STORAGE_BUCKET_NAME),
                remote_path,
                ExtraArgs={"ACL": "public-read", "ContentType": "application/pdf"},
            )

        report_url = f"{settings.AWS_S3_URL_PATH}/{remote_path}#toolbar=0"
        self.report.path = report_url
        self.report.save()
        os.remove(self.local_path)


    def generate_report(self) -> dict:
        message = "Report generation failed"
        success = False

        site, site_error = self._resolve_site()
        if site_error:
            return {"report": self.report, "success": success, "message": site_error}

        lookback_days, lookback_error = self._get_lookback_days()
        if lookback_error:
            return {"report": self.report, "success": success, "message": lookback_error}

        selected_types, type_error = self._normalize_types()
        if type_error:
            return {"report": self.report, "success": success, "message": type_error}

        snapshot = self._build_datasets(selected_types=selected_types, lookback_days=lookback_days)

        info = self.report.info if isinstance(self.report.info, dict) else {}
        info.update(
            {
                "text_color": self.text_color,
                "highlight_color": self.highlight_color,
                "background_color": self.background_color,
                "lookback_days": lookback_days,
                "types": selected_types,
                "snapshot": {
                    "generated_at": snapshot["generated_at"].isoformat(),
                    "window_start": snapshot["window_start"].isoformat(),
                    "site": snapshot["site"],
                    "counts": {
                        "issues": snapshot["datasets"].get("issues", {}).get("count", 0),
                        "tests_pages": len(snapshot["datasets"].get("tests", {}).get("pages", [])),
                        "tests_total": snapshot["datasets"].get("tests", {}).get("rollup", {}).get("total_tests", 0),
                        "caseruns": snapshot["datasets"].get("caseruns", {}).get("count", 0),
                        "performance_pages": len(snapshot["datasets"].get("performance", {}).get("pages", [])),
                    },
                },
            }
        )

        self.report.info = info
        self.report.type = selected_types

        self._render_cover_page(selected_types=selected_types, lookback_days=lookback_days, snapshot=snapshot)
        self._render_sections(selected_types=selected_types, snapshot=snapshot)

        self.publish_report()
        message = "Report Generated"
        success = True

        return {"report": self.report, "success": success, "message": message}

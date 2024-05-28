// custom configurations for Lighthouse CLI
module.exports = {
  extends: 'lighthouse:default',
  plugins: ['lighthouse-plugin-crux'],
  settings: {
    cruxToken: process.env.GOOGLE_CRUX_KEY,
    skipAudits: [
      "full-page-screenshot",
    ],
  },
}
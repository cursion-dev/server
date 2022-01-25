// custom configurations for Lighthouse CLI

module.exports = {
    extends: 'lighthouse:default',
    settings: {
      skipAudits: [
          "full-page-screenshot",
        ],
    },
  };


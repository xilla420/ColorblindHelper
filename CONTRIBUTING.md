# Contributing to Colorblind Helper

Thanks for helping make colours easier to name! Contributions from colour-blind people and artists are especially welcome.

## Ways to help

- **Report a wrong colour name or description.** Open an issue with the HEX code, what the app said, and what you'd
  expect. Plain-language descriptions are tuned by hand in `colorblind_helper/colors.py` (`describe`).
- **Test on macOS or Linux** and tell us what works and what doesn't.
- **Translate** the UI. The strings currently live in `settings_window.py`; i18n is very welcome.
- **Suggest a painting theme.** It must be a public-domain work with a good scan on Wikimedia Commons.

## Development

```bash
pip install -r requirements.txt
python main.py                        # run from source
python -m unittest discover -s tests  # tests
```

Keep pull requests focused, match the existing code style, and add a test when you change colour maths.

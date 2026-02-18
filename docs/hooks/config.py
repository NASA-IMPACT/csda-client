from datetime import date

def on_config(config):
    config.copyright = f"&copy; CC-By NASA, {date.today().year}"
    return config

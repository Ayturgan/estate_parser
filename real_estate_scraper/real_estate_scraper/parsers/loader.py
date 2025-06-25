import yaml
import os

def load_config(config_name_or_path):
    if not config_name_or_path.endswith(".yml") and "/" not in config_name_or_path:
        config_name_or_path = f"real_estate_scraper/configs/{config_name_or_path}.yml"

    full_path = os.path.abspath(config_name_or_path)

    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Config file not found: {full_path}")

    with open(full_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        if config is None:
            raise ValueError(f"Config file is empty or invalid: {full_path}")
        return config
    
    
def extract_value(response_or_selector, selector, all_text=False, multiple=False):
    selector = selector.strip()
    result = None
    extraction_method = 'getall' if multiple else 'get'
    if selector.startswith("xpath:"):
        xpath_sel = selector[len("xpath:"):]
        if xpath_sel.startswith("string("):
            result = response_or_selector.xpath(xpath_sel).get()
        else:
            result = getattr(response_or_selector.xpath(xpath_sel), extraction_method)()
    elif selector.startswith("//") or selector.startswith(".//"):
        if all_text:
            texts = response_or_selector.xpath(selector).getall()
            result = " ".join(t.strip() for t in texts if t.strip())
        else:
            result = getattr(response_or_selector.xpath(selector), extraction_method)()
    else:
        if all_text:
            texts = response_or_selector.css(selector).xpath(".//text()").getall()
            result = " ".join(t.strip() for t in texts if t.strip())
        else:
            result = getattr(response_or_selector.css(selector), extraction_method)()

    if multiple:
        return result if result is not None else []
    else:
        return result.strip() if result else None


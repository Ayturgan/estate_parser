import yaml
import os

def load_config(config_name):
    if not config_name.endswith('.yml'):
        config_name += '.yml'

    full_path = os.path.join('configs', config_name)
    if os.path.exists(full_path):
        with open(full_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    alt_path = os.path.join(base_dir, '..', 'configs', config_name)
    alt_path = os.path.abspath(alt_path)
    if os.path.exists(alt_path):
        with open(alt_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    if os.path.isabs(config_name) and os.path.exists(config_name):
        with open(config_name, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    raise FileNotFoundError(f"Config file not found: {full_path} or {alt_path} or {config_name}")
    
    
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


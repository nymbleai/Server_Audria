def get_all_keys(d, parent_key=''):
    keys = []
    if isinstance(d, dict):
        for k, v in d.items():
            full_key = f"{parent_key}.{k}" if parent_key else k
            keys.append(full_key)
            keys.extend(get_all_keys(v, full_key))
    elif isinstance(d, list):
        for i, item in enumerate(d):
            full_key = f"{parent_key}[{i}]"
            keys.extend(get_all_keys(item, full_key))
    return keys

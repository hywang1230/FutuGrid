
def calculate_fee(price, qty, is_sell, market = 'US'):
    if market == 'HK':
        return 0

    total = price * qty
    fee = max(0.99, round(qty * 0.0049, 2)) + 1 + round(qty * 0.003, 2) \
        + (max(0.01, round(total * 0.0000229, 2)) if is_sell else 0) \
        + (min(5.95, max(0.01, round(qty * 0.000119, 2))) if is_sell else 0)

    return fee


def calculate_amplitude_price(base_price, grid_config, is_up):
    base_price = float(base_price)
    if is_up:
        base_price = base_price * (
                1 + float(grid_config.rise_amplitude)) if grid_config.amplitude_type == 1 \
            else base_price + float(grid_config.rise_amplitude)
    else:
        base_price = base_price * (
                1 - float(grid_config.rise_amplitude)) if grid_config.amplitude_type == 1 \
            else base_price - float(grid_config.rise_amplitude)
    return base_price

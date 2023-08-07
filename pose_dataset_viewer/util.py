def format_size(size):
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    index = 0
    while size >= 1024:
        index += 1
        size /= 1024
    if index == 0:
        return f'{size:.0f} {units[index]}'
    return f'{size:.2f} {units[index]}'


def format_count(size):
    units = ['', ' K', ' M', ' B']
    unit_index = 0
    while size >= 1000 and unit_index < len(units) - 1:
        size /= 1000
        unit_index += 1
    if unit_index == 0:
        return str(size)
    return f'{size:.1f}{units[unit_index]}'

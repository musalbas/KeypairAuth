"""Extra functionality for dealing with dictionaries."""

import collections


def new(old_dict, new_dict, deepness=0, _current_level=0):
    """Compare two dictionaries and return a dictionary containing only the
    added or changed values.

    Set deepness to -1 for infinite recursiveness.

    """
    new_items = {}

    for key, new_value in new_dict.items():
        if key not in old_dict:
            new_items[key] = new_value
        else:
            old_value = old_dict[key]
            if ((deepness == -1 or deepness > _current_level)
                and isinstance(old_value, collections.Mapping)
                and isinstance(new_value, collections.Mapping)):
                new_items[key] = new(old_value, new_value, deepness=deepness,
                                     _current_level=_current_level + 1)
            elif old_value != new_value:
                new_items[key] = new_value

    return new_items


def recursive_update(old_dict, new_dict):
    """Recursive version of dict.update. The new dictionary is returned."""
    for key, new_value in new_dict.items():
        if isinstance(new_value, collections.Mapping):
            old_dict[key] = recursive_update(old_dict.get(key, {}), new_value)
        else:
            old_dict[key] = new_value

    return old_dict

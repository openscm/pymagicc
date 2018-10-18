from copy import deepcopy
import re


# Thank you https://stackoverflow.com/a/15448887/10473080
def _compile_replacement_regexp(rep_dict):
    return re.compile(
        "|".join([re.escape(k) for k in sorted(rep_dict, key=len, reverse=True)]),
        flags=re.DOTALL,
    )


def _multiple_replace(in_str, rep_dict, compiled_regexp):
    out_str = compiled_regexp.sub(lambda x: rep_dict[x.group(0)], in_str)
    return out_str


# def careful_replacement(in_str, old, new, edge_cases):
#     if old in edge_cases.values():
#         for full_str, sub_str in edge_cases.items():
#             avoid_partial_replacement = (
#                 (full_str in in_str) and (sub_str in old) and (not full_str in old)
#             )
#             if avoid_partial_replacement:
#                 return in_str

#     return in_str.replace(old, new)


def _replace_from_replacement_dict(inputs, replacements, inverse=False):
    if inverse:
        replacements = {v: k for k, v in replacements.items()}
    compiled_regexp = _compile_replacement_regexp(replacements)

    inputs_return = deepcopy(inputs)
    if isinstance(inputs_return, str):
        # inputs_return = multiple_replace(inputs_return, old, new, edge_cases)
        inputs_return = _multiple_replace(inputs_return, replacements, compiled_regexp)
    else:
        # inputs_return = [
        #     multiple_replace(v, old, new, edge_cases) for v in inputs_return
        # ]
        inputs_return = [
            _multiple_replace(v, replacements, compiled_regexp) for v in inputs_return
        ]

    return inputs_return

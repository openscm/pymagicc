import pandas as pd

from pymagicc.definitions import (
    convert_magicc7_to_openscm_variables,
    convert_magicc_to_openscm_regions,
)

from .base import _Reader


def find_parameter_groups(columns):
    """
    Find parameter groups within a list

    This finds all the parameters which should be grouped together into tuples rather
    than being separated. For example, if you have a list like
    ``["CORE_CLIMATESENSITIVITY", "RF_BBAER_DIR_WM2", "OUT_ZERO_TEMP_PERIOD_1", "OUT_ZERO_TEMP_PERIOD_2"]``,
    this function will return
    ``{"OUT_ZERO_TEMP_PERIOD": ["OUT_ZERO_TEMP_PERIOD_1", "OUT_ZERO_TEMP_PERIOD_2"]}``
    which tells you that the parameters
    ``["OUT_ZERO_TEMP_PERIOD_1", "OUT_ZERO_TEMP_PERIOD_2"]`` should be grouped
    together into a tuple with the name ``"OUT_ZERO_TEMP_PERIOD"`` while all the other
    columns don't belong to any group.

    Parameters
    ----------
    list of str
        List of strings to sort

    Returns
    -------
    dict of str: list of str
        Dictionary where the keys are the 'group names' and the values are the list of
        parameters which belong to that group name.
    """
    cols_to_merge = {}
    for c in columns:
        toks = c.split("_")
        start = "_".join(toks[:-1])
        if start.lower() in ["file_emisscen", "out_keydata", "file_tuningmodel"]:
            continue

        try:
            int(toks[-1])  # Check if the last token is an integer
            if start not in cols_to_merge:
                cols_to_merge[start] = []
            cols_to_merge[start].append(c)
        except (ValueError, TypeError):
            continue

    return {k: sorted(v) for k, v in cols_to_merge.items()}


class _CompactOutReader(_Reader):
    def read(self):
        compact_table = self._read_compact_table()

        return self._convert_compact_table_to_df_metadata_column_headers(compact_table)

    def _read_compact_table(self):
        with open(self.filepath, "r") as fh:
            headers = self._read_header(fh)
            # TODO: change to reading a limited number of lines
            lines_as_dicts = [line for line in self._read_lines(fh, headers)]

        return pd.DataFrame(lines_as_dicts)

    def _read_header(self, fh):
        line = fh.readline().strip(",\n")
        return [item.strip('"') for item in line.split(",")]

    def _read_lines(self, fh, headers):
        for line in fh:
            toks = line.strip(",\n").split(",")

            if not len(toks) == len(headers):
                raise AssertionError("# headers does not match # lines")

            yield {h: float(v) for h, v in zip(headers, toks)}

    def _convert_compact_table_to_df_metadata_column_headers(self, compact_table):
        ts_cols = [c for c in compact_table if "__" in c]
        para_cols = [c for c in compact_table if "__" not in c]

        ts = compact_table[ts_cols]
        ts = ts.T

        def sort_ts_ids(inid):
            variable, region, year = inid.split("__")
            variable = variable.replace("DAT_", "")

            return {"variable": variable, "region": region, "year": year}

        ts["variable"] = ts.index.map(
            lambda x: convert_magicc7_to_openscm_variables(
                x.split("__")[0].replace("DAT_", "")
            )
        )
        ts["region"] = ts.index.map(
            lambda x: convert_magicc_to_openscm_regions(x.split("__")[1])
        )

        ts["year"] = ts.index.map(lambda x: x.split("__")[2])
        # Make sure all the year strings are four characters long. Not the best test,
        # but as good as we can do for now.
        if not (ts["year"].apply(len) == 4).all():  # pragma: no cover # safety valve
            raise NotImplementedError("Non-annual data not yet supported")

        ts["year"] = ts["year"].astype(int)

        ts = ts.reset_index(drop=True)

        id_cols = {"variable", "region", "year"}
        run_cols = set(ts.columns) - id_cols
        ts = ts.melt(value_vars=run_cols, var_name="run_id", id_vars=id_cols)

        ts["unit"] = "unknown"

        new_index = list(set(ts.columns) - {"value"})
        ts = ts.set_index(new_index)["value"].unstack("year")

        paras = compact_table[para_cols]
        paras.index.name = "run_id"

        cols_to_merge = find_parameter_groups(paras.columns.tolist())

        paras_clean = paras.copy()
        # Aggregate the columns
        for new_col, components in cols_to_merge.items():
            components = sorted(components)
            paras_clean.loc[:, new_col] = tuple(paras[components].values.tolist())
            paras_clean = paras_clean.drop(columns=components)

        years = ts.columns.tolist()
        ts = ts.reset_index().set_index("run_id")
        out = pd.merge(ts, paras_clean, left_index=True, right_index=True).reset_index()

        id_cols = set(out.columns) - set(years)
        out = out.melt(value_vars=years, var_name="year", id_vars=id_cols)
        new_index = list(set(out.columns) - {"value"})

        for c in new_index:
            if isinstance(out[c].values[0], list):
                # ensure can be put in index
                out[c] = out[c].apply(tuple)

        out = out.set_index(new_index)["value"].unstack("year")
        out = out.T

        column_headers = {
            name.lower(): out.columns.get_level_values(name).tolist()
            for name in out.columns.names
        }
        df = out.copy()
        metadata = {}

        return metadata, df, column_headers


class _BinaryCompactOutReader(_CompactOutReader):
    def _read_compact_table(self):
        with open(self.filepath, "rb") as fh:
            headers = self._read_header(fh)
            # can change to reading limited number of lines in future
            lines_as_dicts = [line for line in self._read_lines(fh, headers)]

        return pd.DataFrame(lines_as_dicts)

    def _read_header(self, fh):
        first_value = self._read_item(fh).tobytes()
        if not first_value == b"COMPACT_V1":
            raise AssertionError("Unexpected first value: {}".format(first_value))

        second_value = self._read_item(fh).tobytes()
        if not second_value == b"HEAD":
            raise AssertionError("Unexpected second value: {}".format(second_value))

        items = []
        while True:
            item = self._read_item(fh)
            if item is None or item.tobytes() == b"END":
                break
            items.append(item.tobytes().decode())

        return items

    def _read_lines(self, fh, headers):
        while True:

            items = self._read_item(fh)
            if items is None:
                break

            # Read the values as an array of floats (4 byte)
            items = items.cast("f")
            if len(items) != len(headers):
                raise AssertionError("# headers does not match # lines")

            # Check the line terminator
            item = self._read_item(fh)
            if not item.tobytes() == b"END":
                raise AssertionError(
                    "Unexpected final line value: {}".format(item.tobytes())
                )

            yield {h: float(v) for h, v in zip(headers, items.tolist())}

    def _read_item(self, fh):
        # Fortran writes out a 4 byte integer representing the # of bytes to read for
        # a given chunk, the data and then the size again
        d = fh.read(4)
        if d != b"":
            s = memoryview(d).cast("i")[0]
            item = memoryview(fh.read(s))
            s_after = memoryview(fh.read(4)).cast("i")[0]
            if not s_after == s:
                raise AssertionError(
                    "Wrong size after data. Before: {}. " "After: {}".format(s, s_after)
                )

            return item

import copy
import numpy as np


# TODO: try to generalize using __getattribute__
# TODO: caching
class DataProvider:
    def __init__(self, lasfile):
        self.lasfile = lasfile

    def _find_well_log(self, data):
        if "mnemonic" in data:
            mnemonic = data.pop("mnemonic")
        else:
            mnemonic = ""
        
        for index, log in enumerate(self.lasfile["curve"]):
            log["mnemonic"]
            if log["mnemonic"] == mnemonic:
                log["data"] = self.lasfile["data"][index]
                well_log = log
                break
            else:
                well_log = False

        return well_log

    def _get_well_log_label(self, data):
        data = copy.deepcopy(data)
        well_log = self._find_well_log(data["x"])

        if not well_log:
            msg = f"No well logs found for query: {data}"
            raise ValueError(msg)
        else:
            if well_log["unit"]:
                label = f"{well_log['mnemonic']} ({well_log['unit']})"
            else:
                label = well_log["mnemonic"]
        
        return label

    def get_label(self, data):
        data = copy.deepcopy(data)
        source = data.pop("source", "well_log")
        method = getattr(self, f"_get_{source}_label", None)
        if method is None:
            raise NotImplementedError(f"DataProvider._get_{source}_label")
        label = method(data)
        return label

    # TODO: generalize (all get_* look the same)
    def get_range(self, data):
        data = copy.deepcopy(data)
        source = data.pop("source", "well_logs")
        method = getattr(self, f"_get_{source}_range", None)
        if method is None:
            raise NotImplementedError(f"DataProvider._get_{source}_range")
        rng = method(data)
        return rng

    def get_line(self, data):
        data = copy.deepcopy(data)
        source = data.pop("source", "well_logs")
        method = getattr(self, f"_get_{source}_line", None)
        if method is None:
            raise NotImplementedError(f"DataProvider._get_{source}_line")
        rng = method(data)
        return rng

    def get_marker(self, data):
        print(f"DataProvider.get_marker\n{data}\n")
        raise NotImplementedError("DataProvider.get_marker")

    def get_text(self, data):
        print(f"DataProvider.get_text\n{data}\n")
        raise NotImplementedError("DataProvider.get_text")

    def _get_well_log_data(self, data):
        d = {}
        for k, v in data.items():
            # TODO: process multiples
            well_log = self._find_well_log(v)
            if not well_log:
                msg = f"Well log not found for query {data}"
                raise ValueError(msg)
            d[k] = well_log

        return d

    def _get_well_logs_range(self, data):
        well_log = self._find_well_logs(data)
        if not well_log:
            msg = f"Well log not found for query {data}"
            raise ValueError(msg)
        else:
            npdata = well_log["data"]
            value_range = [
                np.nanmin(npdata),
                np.nanmax(npdata),
            ]

        return value_range

    # def _get_well_logs_line(self, data):
    #     if "alias" in data:
    #         alias = data["alias"]
    #         prop, _ = self.datamanager.get_property_from_mnem(alias)
    #     else:
    #         well_logs = self._find_well_logs(data)
    #         if not well_logs:
    #             msg = f"Well log not found for query {data}"
    #             raise ValueError(msg)
    #         prop = well_logs[0].property

    #     line_prop = prop.default_line_property
    #     if line_prop is None:
    #         line = {"color": "k"}
    #     else:
    #         line = {}
    #         line["color"] = line_prop.color
    #         line["width"] = line_prop.width
    #         line["style"] = line_prop.style
    #         line["alpha"] = line_prop.alpha
    #         line = {k: v for k, v in line.items() if v is not None}

    #     return line

    def get_data(self, data):
        data = copy.deepcopy(data)
        source = data.pop("source", "well_logs")
        method = getattr(self, f"_get_{source}_data", None)
        if method is None:
            raise NotImplementedError(f"DataProvider._get_{source}_data")
        return method(data)

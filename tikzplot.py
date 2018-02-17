import collections as _coll


class TikzElement:
    name = "element"

    def __init__(self, children=None, options=None, name=None):
        if options is not None:
            self.options = OptionList(options)
        else:
            self.options = OptionList()
        if name is not None:
            self.name = name
        if children is None:
            self.children = []
        else:
            self.children = children

    def write(self, file):
        for child in self.children:
            child.write(file)


class TikzCommand(TikzElement):
    name = "cmd"

    def write(self, file):
        file.write("\\{name}".format(name=self.name))
        self.options.write(file)
        file.write("{")
        super().write(file)
        file.write("}\n")


class TikzEnvironment(TikzElement):
    name = "env"

    def write(self, file):
        file.write("\\begin{{{name}}}".format(name=self.name))
        self.options.write(file)
        file.write("\n")
        super().write(file)
        file.write("\\end{{{name}}}\n".format(name=self.name))

    def set(self, key, value):
        self.options[key] = value


class BaseValue:
    pass


class Value(BaseValue):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def write(self, file):
        file.write("{}".format(self.value))


class BaseList:
    def __init__(self, *args, **kwargs):
        super().__init__()
        if args and isinstance(args[0], BaseList):
            options = args[0].values()
        elif kwargs and isinstance(kwargs.get('options',None), BaseList):
            options = kwargs['options'].values()
        else:
            options = dict(*args, **kwargs)
        self.values = _coll.OrderedDict()
        for opt in options.items():
            self[opt[0]] = opt[1]

    def __setitem__(self, key, value):
        if value is None or isinstance(value, BaseValue):
            self.values[key] = value
        else:
            self.values[key] = Value(value)

    def __getitem__(self, item):
        return self.values[item]

    def __contains__(self, item):
        return self.values.__contains__(item)

    def write(self, file):
        for k, v in self.values.items():
            if v is None:
                file.write("{key}, ".format(key=k))
            else:
                file.write("{key}=".format(key=k))
                v.write(file)
                file.write(", ")


class ValueList(BaseList, BaseValue):

    def write(self, file):
        file.write("{")
        super().write(file)
        file.write("}")


class OptionList(BaseList):

    def write(self, file):
        file.write("[")
        BaseList.write(self, file)
        file.write("]")


class Figure(TikzEnvironment):
    name = "tikzpicture"


class Axis(TikzEnvironment):
    name = "axis"


class Plot(TikzCommand):
    name = "addplot"

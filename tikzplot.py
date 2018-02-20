import collections as _coll


class BaseElement:
    def __init__(self):
        self.children=[]

    def write(self, file):
        for child in self.children:
            child.write(file)



class TikzElement(BaseElement):
    name = "element"

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.options = OptionList(*args, **kwargs)

    def __getitem__(self, item):
        return self.options[item]

    def __setitem__(self, key, value):
        self.options[key] = value

    def __repr__(self):
        return "{}({})".format(type(self).__name__,repr(self.options.values))


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


class BaseValue:
    pass


class Value(BaseValue):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def __repr__(self):
        return "{}({})".format(type(self).__name__,repr(self.value))

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

    def __delitem__(self, key):
        del(self.values[key])

    def __contains__(self, item):
        return self.values.__contains__(item)

    def __repr__(self):
        return "{}({})".format(type(self).__name__,repr(self.values))

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

    def axis(self, *args, **kwargs):
        ax = Axis(*args, **kwargs)
        self.children.append(ax)
        return ax


class Axis(TikzEnvironment):
    name = "axis"

    def plot(self, x, y, *args, **kwargs):
        p = Plot(x, y, *args, **kwargs)
        self.children.append(p)
        return p


class Plot(TikzElement):
    name = "addplot"

    def __init__(self, x, y, *args, **kwargs):
        super().__init__(*args, **kwargs)
        coords = Coordinates()
        for xi, yi in zip(x, y):
            coords.children.append(Coordinate2d(xi,yi))
        self.children.append(coords)

    def write(self, file):
        file.write("\\addplot")
        self.options.write(file)
        super().write(file)


class Coordinates(BaseElement):
    def write(self, file):
        file.write("coordinates {\n")
        super().write(file)
        file.write('};')


class Coordinate2d:
    def __init__(self,x, y):
        self.x = x
        self.y = y

    def write(self, file):
        file.write("({}, {})\n".format(self.x, self.y))

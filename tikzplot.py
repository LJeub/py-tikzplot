import collections as _coll
from collections import abc as _type
from numbers import Number
from os import path as _path
from subprocess import run as _run
from shutil import copyfile as _copyfile


class BaseElement:
    def __init__(self):
        self.children=[]

    def __del__(self):
        for child in self.children:
            del(child)


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

    def __delitem__(self, key):
        if key in self.options:
            del(self.options[key])

    def __repr__(self):
        return "{}({})".format(type(self).__name__,repr(self.options))


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
    def write(self, file):
        pass


class Value(BaseValue):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def __repr__(self):
        return "{}({})".format(type(self).__name__,repr(self.value))

    def write(self, file):
        if self.value is not None:
            file.write("{}".format(self.value))


class EncapsulatedValue(BaseValue):
    def __init__(self, value):
        super().__init__()
        if isinstance(value, BaseValue):
            self.value = value
        else:
            self.value = Value(value)

    def __repr__(self):
        return "{}({})".format(type(self).__name__,repr(self.value))

    def write(self, file):
        if self.value is not None:
            file.write('{')
            self.value.write(file)
            file.write('}')


class RGB(Value):
    def __init__(self, *args):
        super().__init__(None)
        if len(args) == 1:
            self.value = args[0]
        elif len(args) == 3:
            self.value = args
        else:
            raise ValueError('wrong number of arguments for color')

    def write(self, file):
        if self.value is not None:
            file.write("{" + "rgb,1:red,{0};green,{1};blue,{2}".format(*self.value) + "}")


class BaseList(_coll.OrderedDict):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.add(*args, **kwargs)

    def __setitem__(self, key, value):
        super().__setitem__(key, as_tikz_value(value))

    def add(self, *args, **kwargs):
        for arg in args:
            if isinstance(arg, _type.Mapping):
                for key, value in arg.items():
                    self[key] = value
            elif isinstance(arg, tuple) and len(arg) == 2:
                self[arg[0]] = arg[1]
            elif isinstance(arg, str) or isinstance(arg, Number):
                self[arg] = None
            elif isinstance(arg, _type.Iterable):
                self.add(arg)
        for key, value in kwargs.items():
            self[key] = value

    def write(self, file):
        for k, v in self.items():
            if v is None:
                file.write("{key}, ".format(key=k))
            else:
                file.write("{key}=".format(key=k))
                v.write(file)
                file.write(", ")


class ValueList(BaseList, BaseValue):

    def write(self, file):
        if self:
            file.write("{")
            super().write(file)
            file.write("}")


class OptionList(BaseList):

    def write(self, file):
        if self:
            file.write("[")
            BaseList.write(self, file)
            file.write("]")


class Figure(TikzEnvironment):
    name = "tikzpicture"
    viewdir = _path.join(_path.dirname(__file__), 'tex')

    def axis(self, *args, **kwargs):
        ax = Axis(*args, **kwargs)
        self.children.append(ax)
        return ax

    def view(self, latex='lualatex'):
        with open(_path.join(self.viewdir, 'view.tikz'), 'w') as f:
            self.write(f)
        verbosity='-silent'
        rv = _run(['latexmk', "-{}".format(latex), "-pv", verbosity, 'viewtemplate.tex'], cwd=self.viewdir)
        if rv.returncode != 0:
            with open(_path.join(self.viewdir, 'viewtemplate.log')) as f:
                print(f.read())

    def save(self, filename, latex='lualatex'):
        with open(_path.join(self.viewdir, 'view.tikz'), 'w') as f:
            self.write(f)
        rv = _run(['latexmk', "-{}".format(latex), "-silent", 'viewtemplate.tex'], cwd=self.viewdir)
        if rv.returncode != 0:
            with open(_path.join(self.viewdir, 'viewtemplate.log')) as f:
                print(f.read())
        else:
            _copyfile(_path.join(self.viewdir, 'viewtemplate.pdf'), filename)


class Axis(TikzEnvironment):
    name = "axis"

    def plot(self, x, y, *args, **kwargs):
        p = Plot(x, y, *args, **kwargs)
        self.children.append(p)
        return p

    def bar(self, x, y, *args, **kwargs):
        p = Plot(x, y, 'ybar', 'ybar legend', 'fill', *args, mark='none', **kwargs)
        self.children.append(p)
        return p

    def hbar(self, x, y, *args, **kwargs):
        p = Plot(x, y, 'xbar', 'xbar legend', 'fill', *args, mark='none', **kwargs)
        self.children.append(p)
        return p


class Label(TikzCommand):
    name = "label"

    def __init__(self, label=None):
        super().__init__()
        if label is not None:
            self.children = [Value(label)]

    def set(self, value):
        if value is None:
            self.children = []
        else:
            self.children = [Value(value)]

    def write(self, file):
        if self.children:
            super().write(file)


class LegendEntry(TikzCommand):
    name='addlegendentry'

    def __init__(self, *args, **kwargs):
        value = None
        if 'legendentry' in kwargs:
            value = kwargs.pop('legendentry')
        elif args:
            value = args[0]
            args = args[1:]
        super().__init__(*args, **kwargs)
        self.set(value)

    def set(self, value):
        if value is None:
            self.children = []
        else:
            self.children = [Value(value)]

    def write(self, file):
        if self.children:
            super().write(file)


class Plot(TikzElement):
    name = "addplot"

    def __init__(self, x, y, *args, texlabel=None, legendentry=None, **kwargs):
        super().__init__(*args, **kwargs)
        coords = Coordinates()
        for xi, yi in zip(x, y):
            coords.children.append(Coordinate2d(xi,yi))
        self.children.append(coords)
        self._label = Label()
        self._legend = LegendEntry()
        self.label = texlabel
        self.legend = legendentry

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, value):
        self._label.set(value)

    @property
    def legend(self):
        return self._legend

    @legend.setter
    def legend(self, value):
        self._legend.set(value)

    def write(self, file):
        file.write("\\addplot+")
        self.options.write(file)
        file.write("\n")
        super().write(file)
        self.label.write(file)
        self.legend.write(file)


class Coordinates(BaseElement):
    def write(self, file):
        file.write("coordinates {\n")
        super().write(file)
        file.write('};\n')


class Coordinate:
    def write(self, file):
        pass


class Coordinate2d(Coordinate, BaseValue):
    def __init__(self,x, y):
        super().__init__()
        self.x = x
        self.y = y

    def write(self, file):
        file.write("({}, {})\n".format(self.x, self.y))


def as_tikz_value(value):
    if isinstance(value, Coordinate):
        return EncapsulatedValue(value)
    elif  isinstance(value, tuple) and isinstance(value[0], Number):
        return EncapsulatedValue(value)
    elif value is None or isinstance(value, BaseValue):
        return value
    elif isinstance(value, _type.Iterable) and not isinstance(value, str):
        return ValueList(value)
    else:
        return Value(value)


class EscapeDict(dict):
    def __missing__(self, key):
        return key


def tikz_escape_value(value):
    escape_dict = EscapeDict({
        '&': r'\&',
        '_': r'\_',
        '$': r'\$',
        '^': r'\^',
        '#': r'\#',
        '%': r'\%',
        '{': r'\{',
        '}': r'\}',
        '\\': r'\textbackslash'
    })
    if isinstance(value, str):
        return "".join(escape_dict[v] for v in value)
    elif isinstance(value, _type.Iterable):
        return [tikz_escape_value(v) for v in value]
    elif isinstance(value, _type.Mapping):
        return type(value)((k, tikz_escape_value(v)) for k, v in value.items())
    else:
        return value

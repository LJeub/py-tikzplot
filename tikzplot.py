import collections as _coll
from collections import abc as _type
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
    pass


class Value(BaseValue):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def __repr__(self):
        return "{}({})".format(type(self).__name__,repr(self.value))

    def write(self, file):
        file.write("{}".format(self.value))


class BaseList(_coll.OrderedDict):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.add(*args, **kwargs)

    def __setitem__(self, key, value):
        if value is None or isinstance(value, BaseValue):
            super().__setitem__(key, value)
        else:
            super().__setitem__(key, Value(value))

    def add(self, *args, **kwargs):
        for arg in args:
            if isinstance(arg, _type.Mapping):
                for key, value in arg.items():
                    self[key] = value
            elif isinstance(arg, tuple) and len(arg) == 2:
                self[arg[0]] = arg[1]
            elif isinstance(arg, str):
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
        p = Plot(x, y, 'ybar', 'ybar legend', 'fill', *args, **kwargs)
        self.children.append(p)
        return p

    def hbar(self, x, y, *args, **kwargs):
        p = Plot(x, y, 'xbar', 'xbar legend', 'fill', *args, **kwargs)
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
        super().__init__(*args, **kwargs)
        value = None
        if 'legendentry' in kwargs:
            value = kwargs.pop('legendentry')
        elif args:
            value = args[0]
            args=args[1:]
        super().__init__(*args,**kwargs)
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
        self._label = Label(texlabel)
        self._legendentry = LegendEntry(legendentry)

    @property
    def legendentry(self):
        return self._legendentry

    @legendentry.setter
    def legendentry(self, value):
        self._legendentry.set(value)

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, value):
        self._label.set(value)

    def write(self, file):
        file.write("\\addplot")
        self.options.write(file)
        file.write("\n")
        super().write(file)
        self.label.write(file)
        self.legendentry.write(file)


class Coordinates(BaseElement):
    def write(self, file):
        file.write("coordinates {\n")
        super().write(file)
        file.write('};\n')


class Coordinate2d:
    def __init__(self,x, y):
        self.x = x
        self.y = y

    def write(self, file):
        file.write("({}, {})\n".format(self.x, self.y))


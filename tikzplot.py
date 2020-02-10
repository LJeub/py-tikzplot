import collections as _coll
from collections import abc as _type
from numbers import Number
from pathlib import Path
from subprocess import run as _run
from shutil import copyfile as _copyfile
from itertools import chain as _chain
from itertools import repeat as _repeat
import tempfile
from pkg_resources import get_distribution, DistributionNotFound
from sklearn.neighbors import KernelDensity
from statistics import stdev
from math import exp


# define __version__
try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    pass


default_viewdir = Path(__file__).resolve().parent / 'tex'


def clean_viewdir():
    """Remove all temporal folders form default viewdir.

    Note that this is not thread-safe and will delete files for currently open figures!
    """
    for f in default_viewdir.iterdir():
        if f.is_dir():
            for fi in f.iterdir():
                fi.unlink()
            f.rmdir()


class BaseElement:
    def __init__(self):
        self.children = []

    def write(self, file):
        for child in self.children:
            child.write(file)


class TikzElement(BaseElement):
    name = "element"

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.options = OptionList(*args, **kwargs)

    def __contains__(self, item):
        return item in self.options

    def __getitem__(self, item):
        return self.options[item]

    def __setitem__(self, key, value):
        self.options[key] = value

    def __delitem__(self, key):
        if key in self.options:
            del(self.options[key])

    def __repr__(self):
        return "{}({})".format(type(self).__name__, repr(self.options))


class TikzCommand(TikzElement):
    name = "cmd"

    def write(self, file):
        file.write("%\n")
        file.write("\\{name}".format(name=self.name))
        self.options.write(file)
        super().write(file)


class Ref(TikzCommand):
    name = 'ref'

    def __init__(self, label):
        super().__init__()
        self.children.append(EncapsulatedValue(label))


class TikzEnvironment(TikzElement):
    name = "env"

    def write(self, file):
        file.write("%\n")
        file.write("\\begin{{{name}}}".format(name=self.name))
        self.options.write(file)
        file.write("%\n")
        super().write(file)
        file.write("%\n")
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
                for arg2 in arg:
                    self.add(arg2)
        for key, value in kwargs.items():
            self[key] = value

    def write(self, file):
        items = list(self.items())

        def write_item(item):
            if item[1] is None:
                file.write("{key}".format(key=item[0]))
            else:
                file.write("{key}=".format(key=item[0]))
                item[1].write(file)

        for item in items[:-1]:
            write_item(item)
            file.write(', ')
        write_item(items[-1])


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
            super().write(file)
            file.write("]")


class Figure(TikzEnvironment):
    name = "tikzpicture"
    index = 0
    viewdir = default_viewdir

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.index = Figure.index + 1
        Figure.index += 1
        self._wdir = tempfile.TemporaryDirectory(dir=self.viewdir)
        self._wdirname = Path(self._wdir.name)

    def axis(self, *args, **kwargs):
        ax = Axis(*args, **kwargs)
        self.children.append(ax)
        return ax

    def subplot(self, *args, **kwargs):
        ax = GroupPlot(*args, **kwargs)
        self.children.append(ax)
        return ax

    def save_tikz(self, filename):
        with open(filename, 'w') as f:
            self.write(f)

    def view(self, latex='lualatex'):
        with open(self._wdirname / 'Figure_{}.tikz'.format(self.index), 'w') as f:
            self.write(f)
        verbosity = '-silent'
        rv = _run(['latexmk', "-{}".format(latex), "-pv", verbosity, "-jobname=Figure_{}".format(self.index),
                   self.viewdir / 'viewtemplate.tex'], cwd=self._wdir.name)
        if rv.returncode != 0:
            with open(self._wdirname / 'Figure_{}.log'.format(self.index)) as f:
                print(f.read())

    def save(self, filename, latex='lualatex'):
        with open(self._wdirname / 'Figure_{}.tikz'.format(self.index), 'w') as f:
            self.write(f)
        rv = _run(['latexmk', "-{}".format(latex), "-silent", "-jobname=Figure_{}".format(self.index),
                  self.viewdir / 'viewtemplate.tex'], cwd=self._wdir.name)
        if rv.returncode != 0:
            with open(self._wdirname / 'Figure_{}.log'.format(self.index)) as f:
                print(f.read())
        else:
            _copyfile(self._wdirname / 'Figure_{}.pdf'.format(self.index), filename)


class Axis(TikzEnvironment):
    name = "axis"

    def plot(self, x, y, *args, **kwargs):
        p = Plot(x, y, *args, **kwargs)
        self.children.append(p)
        return p

    def errorplot(self, x, y, e, *args, **kwargs):
        p = ErrorPlot(x, y, e, *args, **kwargs)
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

    def imshow(self, matrix, *args, colormodel=None, x=None, y=None, **kwargs):
        if x is None:
            x = range(len(matrix[0]))
        elif len(x) != len(matrix[0]):
            if len(x) == 2:
                step = (x[1]-x[0]) / len(matrix[0])
                x = [x[0] + i * step for i in range(len(matrix[0]))]
            else:
                raise ValueError("Provided x value does not match matrix size")

        if y is None:
            y = range(len(matrix))
        elif len(y) != len(matrix):
            if len(y) == 2:
                step = (y[1]-y[0]) / len(matrix)
                y = [y[0] + i * step for i in range(len(matrix))]
            else:
                raise ValueError("Provided y value does not match matrix size")

        x_list = []
        y_list = []
        m_list = []

        for yi, row in zip(y, matrix):
            for xi, m in zip(x, row):
                x_list.append(xi)
                y_list.append(yi)
                m_list.append(m)

        if colormodel is not None:
            m_list = ["{}={}".format(colormodel, mv) for mv in m_list]
            opts = {"point meta": "explicit symbolic", "mesh/color input": "explicit"}
        elif isinstance(matrix[0][0], Number):
            opts = {"point meta": "explicit"}
        else:
            opts = {"point meta": "explicit symbolic", "mesh/color input": "explicit"}
        opts['mesh/cols'] = len(matrix[0])

        p = Plot(x_list, y_list, "matrix plot", "no marks", opts, *args, meta=m_list, **kwargs)

    def violin(self, data,  *args, location=None, orientation='vertical', kd_options=None, grid=100,
               width=0.8, expand_range=3, legendentry=None, texlabel=None, **kwargs):
        data = list(data)
        kd_params = {'bandwidth': 1.06*stdev(data) * len(data)**(-1/5)}
        if kd_options is not None:
            kd_params.update(kd_options)
        kde = KernelDensity(**kd_params)

        if location is None:
            location = sum(isinstance(c, Violin) for c in self.children)

        sf = 0.5*width
        kde.fit([[di] for di in data])
        step = ((max(data) + expand_range*kde.bandwidth) - (min(data) - expand_range*kde.bandwidth)) / grid
        x = [min(data)-expand_range*kde.bandwidth + i*step for i in range(grid)]
        y = kde.score_samples([[xi] for xi in x])
        my = max(y)
        y[:] = [exp(v-my) * sf for v in y]
        p = Violin(x, y, *args, location=location, orientation=orientation, line_options=None, violin_options=None,
             texlabel=texlabel, legendentry=legendentry, **kwargs)
        self.children.append(p)
        return p


class NextPlot(Axis, TikzCommand):
    name = 'nextgroupplot'
    write = TikzCommand.write


class Node(TikzCommand):
    name = "node"

    def __init__(self, *args, value=None, **kwargs):
        super().__init__(*args, **kwargs)
        if value is not None:
            self.value = value

    @property
    def value(self):
        if self.children:
            return self.children[0]
        else:
            return None

    @value.setter
    def value(self, value):
        self.children = [EncapsulatedValue(value)]

    def write(self, file):
        super().write(file)
        file.write(';')


class GroupPlot(TikzEnvironment):
    class XLabel(Node):
        def __init__(self, *args, position='north', **kwargs):
            super().__init__('/pgfplots/every axis label', *args, **kwargs)
            self.position = position

        @property
        def position(self):
            return self._position

        @position.setter
        def position(self, value):

            if value == 'north':
                self['at'] = '(gbox.north)'
                self['anchor'] = 'south'
            elif value == 'south':
                self['at'] = '(gbox.south)'
                self['anchor'] = 'north'
            else:
                raise(ValueError("unknown position {}".format(value)))
            self._position = value

        def write(self, file):
            if self.value is not None:
                super().write(file)

    class YLabel(Node):
        def __init__(self, *args, position='west', **kwargs):

            default_args = ['/pgfplots/every axis label', ('anchor', 'south')]

            super().__init__(*default_args,
                             *args, **kwargs)
            self.position = position

        @property
        def position(self):
            return self._position

        @position.setter
        def position(self, value):
            if value == 'west':
                self['at'] = '(gbox.west)'
                self['rotate'] = 90
            elif value == 'east':
                self['at'] = '(gbox.east)'
                self['rotate'] = 270
            else:
                raise (ValueError("unknown position {}".format(value)))
            self._position = value

        def write(self, file):
            if self.value is not None:
                super().write(file)

    name = 'groupplot'

    def __init__(self, *args, rows=1, cols=1, xlabel=None, ylabel=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = rows
        self.cols = cols
        self.xlabel = xlabel
        self.ylabel = ylabel

    @property
    def xlabel(self):
        return self._xlabel

    @xlabel.setter
    def xlabel(self, value):
        if isinstance(value, _type.Mapping):
            kwargs = {k: v for k, v in value.items() if hasattr(self.XLabel, k)}
            other_args = {k: v for k, v in value.items() if not hasattr(self.XLabel, k)}
            self._xlabel = self.XLabel(other_args, **kwargs)
        else:
            self._xlabel = self.XLabel(value=value)

    @property
    def ylabel(self):
        return self._ylabel

    @ylabel.setter
    def ylabel(self, value):
        if isinstance(value, _type.Mapping):
            kwargs = {k: v for k, v in value.items() if hasattr(self.YLabel, k)}
            other_args = {k: v for k, v in value.items() if not hasattr(self.YLabel, k)}
            self._ylabel = self.YLabel(other_args, **kwargs)
        else:
            self._ylabel = self.YLabel(value=value)

    def nextaxis(self, *args, **kwargs):
        ax = NextPlot(*args, **kwargs)
        self.children.append(ax)
        return ax

    def write(self, file):
        if 'group style' in self:
            go = self['group style']
            if not ('group size' in go or 'columns' in go or 'rows' in go):
                go['columns'] = self.cols
                go['rows'] = self.rows
        else:
            self['group style'] = {'columns': self.cols, 'rows': self.rows}

        file.write(r'\begin{scope}[local bounding box=gbox]')
        super().write(file)
        file.write(r'\end{scope}')
        self.ylabel.write(file)
        self.xlabel.write(file)


class Label(TikzCommand):
    name = "label"

    def __init__(self, label=None):
        super().__init__()
        if label is not None:
            self.children = [EncapsulatedValue(label)]

    def set(self, value):
        if value is None:
            self.children = []
        else:
            self.children = [EncapsulatedValue(value)]

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
            self.children = [EncapsulatedValue(value)]

    def write(self, file):
        if self.children:
            super().write(file)


class Plot(TikzCommand):
    name = "addplot+"

    def __init__(self, x, y, *args, meta=None, texlabel=None, legendentry=None, **kwargs):
        super().__init__(*args, **kwargs)
        if 'mark options' in self.options:
            old_marks = self['mark options']
            self['mark options'] = OptionList({'solid': None, 'fill opacity': 1})
            self['mark options'].add(old_marks)
        coords = Coordinates()
        if not isinstance(meta, _type.Iterable):
            meta = _repeat(meta)
        for xi, yi, mi in zip(x, y, meta):
            coords.children.append(Coordinate2d(xi, yi, meta=mi))
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
        super().write(file)
        self.label.write(file)
        self.legend.write(file)


class Fill(TikzElement):
    name = 'fill between'
    def __init__(self, top, bottom, *args, fill_options=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fill_options = OptionList(fill_options)
        self.fill_options['of'] = '{} and {}'.format(top, bottom)

    def write(self, file):
        file.write('\\addplot+')
        self.options.write(file)
        file.write(' fill between ')
        self.fill_options.write(file)
        file.write(';\n')


class ErrorLegendImage(TikzElement):
    def write(self, file):
        del(self['forget plot'])
        if 'draw' not in self.options:
            self['draw'] = 'none'
        file.write(r'{\fill')
        self.options.write(file)
        file.write('(0cm, -0.1cm) rectangle(0.6cm, 0.1cm);')
        file.write(r'\draw[mark repeat=2,mark phase=2] plot coordinates {(0cm,0cm) (0.3cm,0cm) (0.6cm,0cm)}; }')


class ErrorPlot(TikzElement):
    name = 'ErrorPlot'

    def __init__(self, x, y, e, *args, line_options=None, error_options=None, texlabel=None, legendentry=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.line = Plot(x, y, texlabel=texlabel, legendentry=legendentry)
        self.line.options.add(*args, **kwargs)
        if line_options is not None:
            self.line.options.add(line_options)
        ex = _chain(x, reversed(x))
        ey = _chain((yi + ei[0] for yi, ei in zip(y, e)), (yi-ei[1] for yi, ei in reversed(list(zip(y, e)))))
        self.error = Plot(ex, ey, 'fill', 'forget plot', draw='none', mark='none')
        self.error['fill opacity'] = 0.1
        self.error.options.add(*args, **kwargs)
        self.error.options.add(error_options)
        self.children = [self.error, self.line]

    def __setitem__(self, key, value):
        self.options[key] = value
        self.line[key] = value
        self.error[key] = value

    def __delitem__(self, key):
        if key in self.options:
            del(self.options[key])
            del(self.line[key])
            del(self.error[key])

    def write(self, file):
        self.line['legend image code/.code'] = ErrorLegendImage(self.error.options)
        super().write(file)
        

class Violin(TikzElement):
    class _LegendImage(BaseElement):
        def __init__(self, violin, orientation):
            super().__init__()
            self.violin = violin
            self.orientation = orientation

        def write(self, file):
            violin_opts = OptionList(self.violin.violin.options)
            del violin_opts['forget plot']
            violin_opts['smooth'] = None

            file.write(r'{\path')
            violin_opts.write(file)
            if self.orientation == 'vertical':
                file.write(
                    r' plot coordinates {(0cm, -0.25cm) (-0.1cm, 0cm) (-0.2cm, 0.15cm) (0cm, 0.25cm) (0.2cm, 0.15cm) (0.1cm, 0cm) (0cm, -0.25cm)};')
                file.write(r'\path[mark repeat=2,mark phase=2] plot coordinates {(0cm,-0.3cm) (0cm,0cm) (0cm,0.3cm)}; }')
            elif self.orientation == 'horizontal':
                file.write(
                    r' plot coordinates {(0cm, 0cm) (0.25cm, -0.1cm) (0.4cm, -0.2cm) (0.55cm, 0cm) (0.4cm, 0.2cm) (0.25cm, 0.1cm) (0cm, 0cm)};')
                file.write(r'\path[mark repeat=2,mark phase=2] plot coordinates {(0cm,0cm) (0.3cm,0cm) (0.6cm,0cm)}; }')

    def __init__(self, x, pdf, *args, location=0, orientation='vertical', line_options=None, violin_options=None,
                 texlabel=None, legendentry=None, **kwargs):
        y = [location-p for p in pdf] + [location + p for p in pdf[-1::-1]]
        x_min = min(x)
        x_max = max(x)
        ev = 0.1 * (x_max-x_min)
        if orientation == 'vertical':
            self.violin = Plot(y, x + x[-1::-1])
            self.line = Plot([location]*2, [x_min-ev, x_max+ev],
                             texlabel=texlabel, legendentry=legendentry)
        elif orientation == 'horizontal':
            self.violin = Plot(x + x[-1::-1], y)
            self.line = Plot([x_min - ev, x_max + ev], [location] * 2,
                             texlabel=texlabel, legendentry=legendentry)
        else:
            raise ValueError('Unknown orientation {}'.format(orientation))
        self.line.options.add('no marks', draw='black')
        self.violin.options.add('fill', 'no marks', 'forget plot', draw='none')
        super().__init__(*args, **kwargs)
        self.violin.options.add(violin_options)
        self.children.append(self.violin)
        self.children.append(self.line)
        self._legend = self._LegendImage(self, orientation)

    def __setitem__(self, key, value):
        self.options[key] = value
        self.line[key] = value
        self.violin[key] = value

    def __delitem__(self, key):
        if key in self.options:
            del(self.options[key])
            del(self.line[key])
            del(self.violin[key])

    def write(self, file):
        self.line['legend image code/.code'] = self._legend
        super().write(file)





class Coordinates(BaseElement):
    def write(self, file):
        file.write("%\n")
        file.write("coordinates {\n")
        super().write(file)
        file.write('};\n')


class Coordinate:
    def write(self, file):
        pass


class Coordinate2d(Coordinate, BaseValue):
    def __init__(self, x, y, meta=None):
        super().__init__()
        self.x = x
        self.y = y
        self.meta = meta

    def write(self, file):
        file.write("({}, {})".format(self.x, self.y))
        if self.meta is not None:
            file.write(" [{}]".format(self.meta))
        file.write("\n")


def as_tikz_value(value):
    if isinstance(value, Coordinate):
        return EncapsulatedValue(value)
    elif isinstance(value, tuple) and isinstance(value[0], Number):
        return EncapsulatedValue(value)
    elif value is None or isinstance(value, BaseValue) or isinstance(value, BaseElement):
        return value
    elif isinstance(value, _type.Iterable) and not isinstance(value, str):
        return ValueList(value)
    else:
        return Value(value)


class EscapeDict(dict):
    def __missing__(self, key):
        return key


def tikz_escape_value(value):
    """Use this function to preserve raw text input in the output file, escaping any special latex characters"""
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

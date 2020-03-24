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

    def plot(self, x, y, *args, meta=None, error=None, **kwargs):
        p = CPlot(Coordinates(zip(x, y), error=error, meta=meta), *args, **kwargs)
        self.children.append(p)
        return p

    def errorplot(self, x, y, e, *args, **kwargs):
        p = ErrorPlot(x, y, e, *args, **kwargs)
        self.children.append(p)
        return p

    def bar(self, x, y, *args, **kwargs):
        p = self.plot(x, y, 'ybar', 'ybar legend', 'fill', *args, mark='none', **kwargs)
        return p

    def hbar(self, x, y, *args, **kwargs):
        p = self.plot(x, y, 'xbar', 'xbar legend', 'fill', *args, mark='none', **kwargs)
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
        opts['line join'] = 'miter'
        p = Plot(Coordinates(zip(x_list, y_list), meta=m_list), "matrix plot", "no marks", opts, *args, **kwargs)
        self.children.append(p)

    def violin(self, data,  *args, location=None, orientation='vertical', kd_options=None, grid=100,
               width=0.8, expand_range=3, xmin=None, xmax=None, legendentry=None, texlabel=None, **kwargs):
        data = list(data)
        if len(data) > 1:
            kd_params = {'bandwidth': 1.06*stdev(data) * len(data)**(-1/5)}
        else:
            kd_params = {'bandwidth': 1e-5}

        if kd_options is not None:
            kd_params.update(kd_options)
        kde = KernelDensity(**kd_params)

        if location is None:
            location = sum(isinstance(c, Violin) for c in self.children)

        sf = 0.5*width
        kde.fit([[di] for di in data])
        if xmin is None:
            xmin = min(data) - expand_range*kde.bandwidth
        if xmax is None:
            xmax = max(data) + expand_range*kde.bandwidth
        step = (xmax - xmin) / grid
        x = [xmin + i*step for i in range(grid)]
        y = kde.score_samples([[xi] for xi in x])
        my = max(y)
        y[:] = [exp(v-my) * sf for v in y]
        p = Violin(x, y, *args, location=location, orientation=orientation, line_options=None, violin_options=None,
             texlabel=texlabel, legendentry=legendentry, **kwargs)
        self.children.append(p)
        return p

    def graphic(self, filename, graphic_options, *args, **kwargs):
        p = Plot(Graphic(filename, graphic_options), *args, **kwargs)
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
    name = "addplot"

    def __init__(self, plot_data, *args, texlabel=None, legendentry=None, **kwargs):
        super().__init__(*args, **kwargs)
        if 'mark options' in self.options:
            old_marks = self['mark options']
            self['mark options'] = OptionList({'solid': None, 'fill opacity': 1})
            self['mark options'].add(old_marks)

        self.children.append(plot_data)
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


class CPlot(Plot):
    name = "addplot+"


class Graphic(TikzElement):
    name = "graphics"
    def __init__(self, filename, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filename = filename

    def write(self, file):
        file.write(" ")
        file.write(self.name)
        self.options.write(file)
        file.write('{"' + str(self.filename) + '"};')


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


class ErrorPlot(TikzElement):
    name = 'ErrorPlot'

    class _LegendImage(TikzElement):
        def write(self, file):
            if 'forget plot' in self:
                del (self['forget plot'])
            if 'draw' not in self.options:
                self['draw'] = 'none'
            file.write(r'{\fill')
            self.options.write(file)
            file.write('(0cm, -0.1cm) rectangle(0.6cm, 0.1cm);')
            file.write(r'\draw[mark repeat=2,mark phase=2] plot coordinates {(0cm,0cm) (0.3cm,0cm) (0.6cm,0cm)}; }')

    def __init__(self, x, y, e, *args, line_options=None, error_options=None, texlabel=None, legendentry=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.line = CPlot(Coordinates(zip(x, y)), texlabel=texlabel, legendentry=legendentry)
        self.line.options.add(*args, **kwargs)
        if line_options is not None:
            self.line.options.add(line_options)
        ex = _chain(x, reversed(x))
        ey = _chain((yi + ei[0] for yi, ei in zip(y, e)), (yi-ei[1] for yi, ei in reversed(list(zip(y, e)))))
        self.error = CPlot(Coordinates(zip(ex, ey)), 'fill', 'forget plot', draw='none', mark='none')
        self.error['fill opacity'] = 0.1
        self.error.options.add(*args, **kwargs)
        self.error.options.add(error_options)
        self.children = [self.error, self.line]

    def write(self, file):
        old_line_opts = self.line.options
        old_error_opts = self.error.options
        self.line.options = OptionList({'legend image code/.code': self._LegendImage(self.error.options)},
                                       self.options, old_line_opts)
        self.error.options = OptionList(self.options, old_error_opts)
        super().write(file)
        self.line.options = old_line_opts
        self.error.options = old_error_opts
        

class Violin(TikzElement):
    name = 'Violin'

    class _LegendImage(BaseElement):
        def __init__(self, violin, orientation):
            super().__init__()
            self.violin = violin
            self.orientation = orientation

        def write(self, file):
            line_opts = OptionList(self.violin.line.options)
            if 'forget plot' in line_opts:
                del line_opts['forget plot']
            line_opts.add('/pgfplots/.cd', {'mark repeat': 2, 'mark phase': 2})

            file.write(r'{\path[/pgfplots/.cd, smooth]')
            if self.orientation == 'vertical':
                file.write(
                    r' plot coordinates {(0.0cm, 0.3cm) (0.2cm, 0.125cm) (0.1cm, 0.0cm) (0.0cm, -0.3cm) (-0.1cm, 0.0cm) (-0.2cm, 0.125cm) (0.0cm, 0.3cm)};')
                file.write(r'\path')
                line_opts.write(file)
                file.write(r' plot coordinates {(0cm,-0.3cm) (0cm,0cm) (0cm,0.3cm)}; }')
            elif self.orientation == 'horizontal':
                file.write(
                    r' plot coordinates {(0.0cm, 0.0cm) (0.175cm, 0.2cm) (0.3cm, 0.1cm) (0.6cm, 0.0cm) (0.3cm, -0.1cm) (0.175cm, -0.2cm) (0.0cm, 0.0cm)};')
                file.write(r'\path')
                line_opts.write(file)
                file.write(r' plot coordinates {(0cm,0cm) (0.3cm,0cm) (0.6cm,0cm)}; }')

    def __init__(self, x, pdf, *args, location=0, orientation='vertical', line_options=None, violin_options=None,
                 texlabel=None, legendentry=None, **kwargs):
        y = [location-p for p in pdf] + [location + p for p in pdf[-1::-1]]
        x_min = min(x)
        x_max = max(x)
        if orientation == 'vertical':
            self.violin = CPlot(Coordinates(zip(y, x + x[-1::-1])))
            self.line = Plot(Coordinates([(location, x_min), (location, x_max)]),
                             texlabel=texlabel, legendentry=legendentry)
        elif orientation == 'horizontal':
            self.violin = CPlot(Coordinates(zip(x + x[-1::-1], y)))
            self.line = Plot(Coordinates([(x_min, location), (x_max, location)]),
                             texlabel=texlabel, legendentry=legendentry)
        else:
            raise ValueError('Unknown orientation {}'.format(orientation))
        self.line.options.add('thin', 'no marks', 'forget plot', draw='black')
        self.violin.options.add('fill', 'no marks', draw='none')
        super().__init__(*args, **kwargs)
        self.violin.options.add(violin_options)
        self.line.options.add(line_options)
        self.children.append(self.violin)
        self.children.append(self.line)
        self._legend = self._LegendImage(self, orientation)

    def write(self, file):
        old_line_opts = self.line.options
        old_violin_opts = self.violin.options
        self.line.options = OptionList(self.options, old_line_opts)
        self.violin.options = OptionList({'legend image code/.code': self._legend}, self.options, old_violin_opts)
        super().write(file)
        self.line.options = old_line_opts
        self.violin.options = old_violin_opts


class Coordinates(BaseElement):
    def __init__(self, data, error=None, meta=None):
        super().__init__()
        if error is None:
            error = _repeat(None)
        if meta is None:
            meta = _repeat(None)
        for d, e, m in zip(data, error, meta):
            self.children.append(Coordinate(d, e, m))

    def write(self, file):
        file.write("%\n")
        file.write("coordinates {\n")
        super().write(file)
        file.write('};\n')


class Coordinate(BaseValue):
    def __init__(self, point, error=None, meta=None):
        super().__init__()
        self.point = point
        self.error = error
        self.meta = meta

    def write(self, file):
        file.write(str(self.point))
        if self.error is not None:
            file.write(" +- {}".format(self.error))
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

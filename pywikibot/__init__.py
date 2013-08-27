# -*- coding: utf-8  -*-
"""
The initialization file for the Pywikibot framework.
"""
#
# (C) Pywikibot team, 2008-213
#
# Distributed under the terms of the MIT license.
#
__release__ = '2.0b1'
__version__ = '$Id$'

import datetime
import difflib
import logging
import math
import re
import sys
import threading
from Queue import Queue

# Use pywikibot. prefix for all in-package imports; this is to prevent
# confusion with similarly-named modules in version 1 framework, for users
# who want to continue using both

from pywikibot import config2 as config
from pywikibot.bot import *
from pywikibot.exceptions import *
from pywikibot.textlib import *
from pywikibot.i18n import translate


class Timestamp(datetime.datetime):
    """Class for handling Mediawiki timestamps.

    This inherits from datetime.datetime, so it can use all of the methods
    and operations of a datetime object.  To ensure that the results of any
    operation are also a Timestamp object, be sure to use only Timestamp
    objects (and datetime.timedeltas) in any operation.

    Use Timestamp.fromISOformat() and Timestamp.fromtimestampformat() to
    create Timestamp objects from Mediawiki string formats.

    Use Site.getcurrenttime() for the current time; this is more reliable
    than using Timestamp.utcnow().

    """
    mediawikiTSFormat = "%Y%m%d%H%M%S"
    ISO8601Format = "%Y-%m-%dT%H:%M:%SZ"

    @classmethod
    def fromISOformat(cls, ts):
        """Convert an ISO 8601 timestamp to a Timestamp object."""
        return cls.strptime(ts, cls.ISO8601Format)

    @classmethod
    def fromtimestampformat(cls, ts):
        """Convert the internal MediaWiki timestamp format to a Timestamp object."""
        return cls.strptime(ts, cls.mediawikiTSFormat)

    def toISOformat(self):
        """Converts the Timestamp object to an ISO 8601 timestamp"""
        return self.strftime(self.ISO8601Format)

    def totimestampformat(self):
        """Converts the Timestamp object to the internal MediaWiki timestamp format."""
        return self.strftime(self.mediawikiTSFormat)

    def __str__(self):
        """Return a string format recognized by the API"""
        return self.toISOformat()

    def __add__(self, other):
        newdt = datetime.datetime.__add__(self, other)
        if isinstance(newdt, datetime.datetime):
            return Timestamp(newdt.year, newdt.month, newdt.day, newdt.hour,
                             newdt.minute, newdt.second, newdt.microsecond,
                             newdt.tzinfo)
        else:
            return newdt

    def __sub__(self, other):
        newdt = datetime.datetime.__sub__(self, other)
        if isinstance(newdt, datetime.datetime):
            return Timestamp(newdt.year, newdt.month, newdt.day, newdt.hour,
                             newdt.minute, newdt.second, newdt.microsecond,
                             newdt.tzinfo)
        else:
            return newdt


class Coordinate(object):
    """
    Class for handling and storing Coordinates.
    For now its just being used for DataSite, but
    in the future we can use it for the GeoData extension.
    """
    def __init__(self, lat, lon, alt=None, precision=None, globe='earth',
                 typ="", name="", dim=None, site=None, entity=''):
        """
        @param lat: Latitude
        @type lat: float
        @param lon: Longitute
        @type lon: float
        @param alt: Altitute? TODO FIXME
        @param precision: precision
        @type precision: float
        @param globe: Which globe the point is on
        @type globe: str
        @param typ: The type of coordinate point
        @type typ: str
        @param name: The name
        @type name: str
        @param dim: Dimension (in meters)
        @type dim: int
        @param entity: The url entity of a Wikibase item
        @type entity: str
        """
        self.lat = lat
        self.lon = lon
        self.alt = alt
        self._precision = precision
        if globe:
            globe = globe.lower()
        self.globe = globe
        self._entity = entity
        self.type = typ
        self.name = name
        self._dim = dim
        if not site:
            self.site = Site().data_repository()
        else:
            self.site = site

    def __repr__(self):
        string = 'Coordinate(%s, %s' % (self.lat, self.lon)
        if self.globe != 'earth':
            string += ', globe="%s"' % self.globe
        string += ')'
        return string

    @property
    def entity(self):
        if self._entity:
            return self._entity
        return self.site.globes()[self.globe]

    def toWikibase(self):
        """
        Function which converts the data to a JSON object
        for the Wikibase API.
        FIXME Should this be in the DataSite object?
        """
        if not self.globe in self.site.globes():
            raise NotImplementedError(u"%s is not supported in Wikibase yet." % self.globe)
        return {'latitude': self.lat,
                'longitude': self.lon,
                'altitude': self.alt,
                'globe': self.entity,
                'precision': self.precision,
                }

    @staticmethod
    def fromWikibase(data, site):
        """Constructor to create an object from Wikibase's JSON output"""
        globes = {}
        for k in site.globes():
            globes[site.globes()[k]] = k

        globekey = data['globe']
        if globekey:
            globe = globes.get(data['globe'])
        else:
            # Default to earth or should we use None here?
            globe = 'earth'

        return Coordinate(data['latitude'], data['longitude'],
                          data['altitude'], data['precision'],
                          globe, site=site, entity=data['globe'])

    @property
    def precision(self):
        """
        The biggest error (in degrees) will be given by the longitudinal error - the same error in meters becomes larger
        (in degrees) further up north. We can thus ignore the latitudinal error.

        The longitudinal can be derived as follows:

        In small angle approximation (and thus in radians):

        Δλ ≈ Δpos / r_φ, where r_φ is the radius of earth at the given latitude. Δλ is the error in longitude.

           r_φ = r cos φ, where r is the radius of earth, φ the latitude

        Therefore: precision = math.degrees( self._dim / ( radius * math.cos( math.radians( self.lat ) ) ) )
        """
        if not self._precision:
            radius = 6378137  # TODO: Support other globes
            self._precision = math.degrees(self._dim / (radius * math.cos(math.radians(self.lat))))
        return self._precision

    def precisionToDim(self):
        """Convert precision from Wikibase to GeoData's dim"""
        raise NotImplementedError


class WbTime(object):
    """ A Wikibase time representation"""

    PRECISION = {'1000000000': 0, '100000000': 1, '10000000': 2, '1000000': 3, '100000': 4, '10000': 5, 'millenia': 6, 'century': 7, 'decade': 8, 'year': 9, 'month': 10, 'day': 11, 'hour': 12, 'minute': 13, 'second': 14}
    FORMATSTR = '{0:+012d}-{1:02d}-{2:02d}T{3:02d}:{4:02d}:{5:02d}Z'

    def __init__(self, year=None, month=None, day=None, hour=None, minute=None, second=None, precision=None, before=0, after=0, timezone=0, calendarmodel='http://www.wikidata.org/entity/Q1985727'):
        """ Creates a new WbTime object. The precision can be set by the Wikibase int value (0-14) or by a human readable string, e.g., 'hour'. If no precision is given, it is set according to the given time units."""
        if year is None:
            raise ValueError('no year given')
        self.precision = WbTime.PRECISION['second']
        if second is None:
            self.precision = WbTime.PRECISION['minute']
            second = 0
        if minute is None:
            self.precision = WbTime.PRECISION['hour']
            minute = 0
        if hour is None:
            self.precision = WbTime.PRECISION['day']
            hour = 0
        if day is None:
            self.precision = WbTime.PRECISION['month']
            day = 1
        if month is None:
            self.precision = WbTime.PRECISION['year']
            month = 1
        self.year = long(year)
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second
        self.after = after
        self.before = before
        self.timezone = timezone
        self.calendarmodel = calendarmodel

        # if precision is given it overwrites the autodetection above
        if precision is not None:
            if isinstance(precision, int):
                self.precision = precision
            elif precision in WbTime.PRECISION:
                self.precision = WbTime.PRECISION[precision]
            else:
                raise ValueError('Invalid precision: "%s"' % precision)

    @staticmethod
    def fromTimestr(datetimestr, precision=14, before=0, after=0, timezone=0, calendarmodel='http://www.wikidata.org/entity/Q1985727'):
        match = re.match('([-+]?\d+)-(\d+)-(\d+)T(\d+):(\d+):(\d+)Z', datetimestr)
        if not match:
            raise ValueError(u"Invalid format: '%s'" % datetimestr)
        t = match.groups()
        return WbTime(long(t[0]), int(t[1]), int(t[2]), int(t[3]), int(t[4]), int(t[5]), precision, before, after, timezone, calendarmodel)

    def toWikibase(self):
        """
        Function which converts the data to a JSON object
        for the Wikibase API.
        """
        json = {'time': WbTime.FORMATSTR.format(self.year, self.month, self.day,
                self.hour, self.minute, self.second),
                'precision': self.precision,
                'after': self.after,
                'before': self.before,
                'timezone': self.timezone,
                'calendarmodel': self.calendarmodel
                }
        return json

    @staticmethod
    def fromWikibase(ts):
        return WbTime.fromTimestr(ts[u'time'], ts[u'precision'], ts[u'before'], ts[u'after'], ts[u'timezone'], ts[u'calendarmodel'])

    def __str__(self):
        return str(self.toWikibase())

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __repr__(self):
        return u"WbTime(year=%(year)d, month=%(month)d, day=%(day)d, " \
            u"hour=%(hour)d, minute=%(minute)d, second=%(second)d, " \
            u"precision=%(precision)d, before=%(before)d, after=%(after)d, " \
            u"timezone=%(timezone)d, calendarmodel='%(calendarmodel)s')" % self.__dict__


def deprecated(instead=None):
    """Decorator to output a method deprecation warning.

    @param instead: if provided, will be used to specify the replacement
    @type instead: string
    """
    def decorator(method):
        def wrapper(*args, **kwargs):
            funcname = method.func_name
            classname = args[0].__class__.__name__
            if instead:
                warning(u"%s.%s is DEPRECATED, use %s instead."
                        % (classname, funcname, instead))
            else:
                warning(u"%s.%s is DEPRECATED." % (classname, funcname))
            return method(*args, **kwargs)
        wrapper.func_name = method.func_name
        return wrapper
    return decorator


def deprecate_arg(old_arg, new_arg):
    """Decorator to declare old_arg deprecated and replace it with new_arg"""
    _logger = ""

    def decorator(method):
        def wrapper(*__args, **__kw):
            meth_name = method.__name__
            if old_arg in __kw:
                if new_arg:
                    if new_arg in __kw:
                        pywikibot.warning(
u"%(new_arg)s argument of %(meth_name)s replaces %(old_arg)s; cannot use both."
                            % locals())
                    else:
                        pywikibot.warning(
u"%(old_arg)s argument of %(meth_name)s is deprecated; use %(new_arg)s instead."
                            % locals())
                        __kw[new_arg] = __kw[old_arg]
                else:
                    pywikibot.debug(
u"%(old_arg)s argument of %(meth_name)s is deprecated."
                        % locals(), _logger)
                del __kw[old_arg]
            return method(*__args, **__kw)
        wrapper.__doc__ = method.__doc__
        wrapper.__name__ = method.__name__
        return wrapper
    return decorator


_sites = {}


def Site(code=None, fam=None, user=None, sysop=None, interface=None):
    """Return the specified Site object.

    Returns a cached object if possible, otherwise instantiates a new one.

    @param code: language code
    @type code: string
    @param fam: family name or object
    @type fam: string or Family
    @param user: bot user name to use on this site
    @type user: unicode

    """
    _logger = "wiki"

    if code is None:
        code = config.mylang
    if fam is None:
        fam = config.family
    if user is None:
        try:
            user = config.usernames[fam][code]
        except KeyError:
            user = None
    if user is None:
        try:
            user = config.usernames[fam]['*']
        except KeyError:
            user = None
    if sysop is None:
        try:
            sysop = config.sysopnames[fam][code]
        except KeyError:
            sysop = None
    if interface is None:
        interface = config.site_interface
    try:
        tmp = __import__('pywikibot.site', fromlist=[interface])
        __Site = getattr(tmp, interface)
    except ImportError:
        raise ValueError("Invalid interface name '%(interface)s'" % locals())
    key = '%s:%s:%s' % (fam, code, user)
    if not key in _sites or not isinstance(_sites[key], __Site):
        _sites[key] = __Site(code=code, fam=fam, user=user, sysop=sysop)
        pywikibot.debug(u"Instantiating Site object '%(site)s'"
                        % {'site': _sites[key]}, _logger)
    return _sites[key]


getSite = Site  # alias for backwards-compability


from page import Page, ImagePage, Category, Link, User, ItemPage, PropertyPage, Claim
from page import html2unicode, url2unicode


link_regex = re.compile(r'\[\[(?P<title>[^\]|[<>{}]*)(\|.*?)?\]\]')


def setAction(s):
    """Set a summary to use for changed page submissions"""
    config.default_edit_summary = s


def showDiff(oldtext, newtext):
    """
    Output a string showing the differences between oldtext and newtext.
    The differences are highlighted (only on compatible systems) to show which
    changes were made.

    """
    # This is probably not portable to non-terminal interfaces....
    # For information on difflib, see http://pydoc.org/2.3/difflib.html
    color = {
        '+': 'lightgreen',
        '-': 'lightred',
    }
    diff = u''
    colors = []
    # This will store the last line beginning with + or -.
    lastline = None
    # For testing purposes only: show original, uncolored diff
    #     for line in difflib.ndiff(oldtext.splitlines(), newtext.splitlines()):
    #         print line
    for line in difflib.ndiff(oldtext.splitlines(), newtext.splitlines()):
        if line.startswith('?'):
            # initialize color vector with None, which means default color
            lastcolors = [None for c in lastline]
            # colorize the + or - sign
            lastcolors[0] = color[lastline[0]]
            # colorize changed parts in red or green
            for i in range(min(len(line), len(lastline))):
                if line[i] != ' ':
                    lastcolors[i] = color[lastline[0]]
            diff += lastline + '\n'
            # append one None (default color) for the newline character
            colors += lastcolors + [None]
        elif lastline:
            diff += lastline + '\n'
            # colorize the + or - sign only
            lastcolors = [None for c in lastline]
            lastcolors[0] = color[lastline[0]]
            colors += lastcolors + [None]
        lastline = None
        if line[0] in ('+', '-'):
            lastline = line
    # there might be one + or - line left that wasn't followed by a ? line.
    if lastline:
        diff += lastline + '\n'
        # colorize the + or - sign only
        lastcolors = [None for c in lastline]
        lastcolors[0] = color[lastline[0]]
        colors += lastcolors + [None]

    result = u''
    lastcolor = None
    for i in range(len(diff)):
        if colors[i] != lastcolor:
            if lastcolor is None:
                result += '\03{%s}' % colors[i]
            else:
                result += '\03{default}'
        lastcolor = colors[i]
        result += diff[i]
    output(result)


# Throttle and thread handling

stopped = False


def stopme():
    """Drop this process from the throttle log, after pending threads finish.

    Can be called manually if desired, but if not, will be called automatically
    at Python exit.

    """
    global stopped
    _logger = "wiki"

    if not stopped:
        pywikibot.debug(u"stopme() called", _logger)

        def remaining():
            import datetime
            remainingPages = page_put_queue.qsize() - 1
                # -1 because we added a None element to stop the queue
            remainingSeconds = datetime.timedelta(
                seconds=(remainingPages * config.put_throttle))
            return (remainingPages, remainingSeconds)

        page_put_queue.put((None, [], {}))
        stopped = True

        if page_put_queue.qsize() > 1:
            output(u'Waiting for %i pages to be put. Estimated time remaining: %s'
                   % remaining())

        while(_putthread.isAlive()):
            try:
                _putthread.join(1)
            except KeyboardInterrupt:
                answer = inputChoice(u"""\
There are %i pages remaining in the queue. Estimated time remaining: %s
Really exit?""" % remaining(),
                    ['yes', 'no'], ['y', 'N'], 'N')
                if answer == 'y':
                    return

    # only need one drop() call because all throttles use the same global pid
    try:
        _sites.values()[0].throttle.drop()
        pywikibot.log(u"Dropped throttle(s).")
    except IndexError:
        pass

import atexit
atexit.register(stopme)


# Create a separate thread for asynchronous page saves (and other requests)
def async_manager():
    """Daemon; take requests from the queue and execute them in background."""
    while True:
        (request, args, kwargs) = page_put_queue.get()
        if request is None:
            break
        request(*args, **kwargs)


def async_request(request, *args, **kwargs):
    """Put a request on the queue, and start the daemon if necessary."""
    if not _putthread.isAlive():
        try:
            page_put_queue.mutex.acquire()
            try:
                _putthread.start()
            except (AssertionError, RuntimeError):
                pass
        finally:
            page_put_queue.mutex.release()
    page_put_queue.put((request, args, kwargs))

# queue to hold pending requests
page_put_queue = Queue(config.max_queue_size)
# set up the background thread
_putthread = threading.Thread(target=async_manager)
# identification for debugging purposes
_putthread.setName('Put-Thread')
_putthread.setDaemon(True)

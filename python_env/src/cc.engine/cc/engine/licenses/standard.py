import grok
from zope.interface import implements
from zope.publisher.interfaces import NotFound
from zope.i18n import translate

import cc.license
from cc.engine import i18n
from cc.license.exceptions import LicenseException

from cc.engine import interfaces
from cc.license.decorators import memoized

class BrowserLicense(grok.Model):
    implements(interfaces.ILicense)

    TARGET_NAMES = ('deed', 'rdf', 'rdf-checksum',
                    'legalcode', 'legalcode-checksum')

    def __init__(self, parent, pieces):
        self.__parent__ = parent
        self.__name__ = pieces[-1]

        self.pieces = pieces
        
    @property
    @memoized
    def license(self):
        """Return the cc.license.License object selected."""

        # decode the version and jurisdiction
        if len(self.pieces) > 2:
            version, jurisdiction = self.pieces[1:3]
        elif len(self.pieces) > 1:
            version, jurisdiction = self.pieces[1], None
        else:
            version, jurisdiction = None, None
            
        return cc.license.LicenseFactory().by_license_code(self.pieces[0],
                                                           version,
                                                           jurisdiction)

    @property
    @memoized
    def conditions(self):
        """Return a sequence of mappings defining the conditions defined by
        this license."""

        attrs = []

        for lic in self.license.code.split('-'):

            # Go through the chars and build up the HTML and such
            char_title = translate ('char.%s_title' % lic,
                                    domain='icommons')
            char_brief = translate ('char.%s_brief' % lic,
                                    domain='icommons')

            icon_name = lic
            predicate = 'cc:requires'
            object = 'http://creativecommons.org/ns#Attribution'

            if lic == 'nc':
              predicate = 'cc:prohibits'
              object = 'http://creativecommons.org/ns#CommercialUse'
              if self.license.jurisdiction == 'jp':
                 icon_name = '%s-jp' % icon_name
              elif self.license.jurisdiction in ('fr', 'es', 'nl', 'at', 'fi', 'be', 'it'):
                 icon_name = '%s-eu' % icon_name
            elif lic == 'sa':
              object = 'http://creativecommons.org/ns#ShareAlike'
              if self.license.version == 3.0 and self.license.code == 'by-sa':
                char_brief = translate ('char.sa_bysa30_brief',
                                        domain='icommons')
            elif lic == 'nd':
              predicate = ''
              object = ''

            attrs.append({'char_title':char_title,
                          'char_brief':char_brief,
                          'icon_name':icon_name,
                          'char_code':lic,
                          'predicate':predicate,
                          'object':object,
                     })

        return attrs
        
    def traverse(self, name):

        if len(self.pieces) > 4:
            # no cases call for more than four steps of traversal:
            # code, version [jurisdiction], [deed.xx]
            return None

        # handle deed.de, etc -- these shouldn't trigger views, but also
        # shouldn't be added to our traversal stack
        if name[:5] == 'deed.': 
            return self

        if name not in self.TARGET_NAMES:
            # make sure we always return the same class since
            # views are registered for particular classes
            return self.__class__(self, self.pieces + [name])

class LicenseDeed(grok.View):
    grok.context(BrowserLicense)
    grok.name('index')
    grok.template('deed')

    def update(self):
        """Prepare to render the deed."""

        # redirect if this isn't deed.xx and we don't have a trailing slash
        if self.request['PATH_INFO'].split('/')[-1].split('.', 1)[0] != 'deed':
            if self.request['PATH_INFO'][-1] != '/':
                if self.request.get('QUERY_STRING', ''):
                    target = '%s/?%s' % (self.request['PATH_INFO'],
                                         self.request['QUERY_STRING'])
                else:
                    target = '%s/' % self.request['PATH_INFO']

                return self.request.response.redirect(target)

        # make sure we've traversed to a valid license version
        try:
            self.context.license
            
        except LicenseException, e:
            raise NotFound(self.context, self.request['REQUEST_URI'],
                           self.request)

        # make sure we've extracted the locale from the request querystring
        self.request.setupLocale()

    @property
    def is_rtl(self):
        """Return 'rtl' if the request locale is represented right-to-left;
        otherwise return an empty string."""

        if self.request.locale.orientation.characters == u'right-to-left':
            return 'rtl'

        return ''

    @property
    def is_rtl_align(self):
        """Return the appropriate alignment for the request locale:
        'right' or 'left'."""

        return self.request.locale.orientation.characters.split('-')[0]

    @property
    def multi_language(self):
        """Return True if the legalcode for this license is available in
        multiple languages (or a single language with a language code different
        than that of the jurisdiction.
        
        ZZZ i18n information like this should really be stored outside of
        the presentation layer; we don't maintain it anywhere right now, so
        here it is.
        """

        if self.context.license.jurisdiction in ('es', 'ca', 'be', 'ch'):
            return True

        return False
   
    @property
    def color(self):
        """Return the "color" of the license; the color reflects the relative
        amount of freedom."""
        
        license_code = self.context.license.code
        
        if license_code.lower() in ('devnations', 'sampling'):
           return 'red'
       
        elif license_code.find('sampling') > -1 or \
                 license_code.find('nc') > -1 or \
                 license_code.find('nd') > -1:
           return 'yellow'
       
        else:
           return 'green'

class LicenseRdf(grok.View):
    grok.context(BrowserLicense)
    grok.name('rdf')

    def render(self):
        """Return the RDF+XML for this license."""
        
        self.request.response.setHeader(
            'Content-Type', 'application/rdf+xml; charset=UTF-8')

        return self.context.license.rdf
                     

# -*- coding: utf-8  -*-
"""Objects representing Flow entities, like boards, topics, and posts."""
#
# (C) Pywikibot team, 2015
#
# Distributed under the terms of the MIT license.
#
from __future__ import unicode_literals

__version__ = '$Id$'

import logging

from pywikibot.page import BasePage


logger = logging.getLogger('pywiki.wiki.flow')


# Flow page-like objects (boards and topics)
class FlowPage(BasePage):

    """
    The base page for the Flow extension.

    There should be no need to instantiate this directly.

    Subclasses must provide a _load() method to load and cache
    the object's internal data from the API.
    """

    def __init__(self, source, title=''):
        """Constructor.

        @param source: A Flow-enabled site or a Link or Page on such a site
        @type source: Site, Link, or Page
        @param title: normalized title of the page
        @type title: unicode

        @raise TypeError: incorrect use of parameters
        @raise ValueError: use of non-Flow-enabled Site
        """
        super(FlowPage, self).__init__(source, title)

        if not self.site.has_extension('Flow'):
            raise ValueError('site is not Flow-enabled')

    def _load_uuid(self):
        """Load and save the UUID of the page."""
        self._uuid = self._load()['workflowId']

    @property
    def uuid(self):
        """Return the UUID of the page.

        @return: UUID of the page
        @rtype: unicode
        """
        if not hasattr(self, '_uuid'):
            self._load_uuid()
        return self._uuid

    def get(self, force=False, get_redirect=False, sysop=False):
        if get_redirect or force or sysop:
            raise NotImplementedError

        # TODO: Return more useful data
        return self._data


class Board(FlowPage):

    """A Flow discussion board."""

    def _load(self, **kwargs):
        """Load and cache the Board's data, derived from its topic list."""
        if not hasattr(self, '_data'):
            self._data = self.site.load_board(self, **kwargs)
        return self._data

    def topics(self, **kwargs):
        """Load this board's topics."""
        def _parse_url(links):
            """Parse a URL retrieved from the API."""
            rule = links.values()[0]
            params = {}
            url = rule['url']
            query_string = url.split('?')[1]
            args = query_string.split('&')
            for arg in args:
                key, value = arg.split('=')
                if key == 'title':
                    params['page'] = value
                else:
                    key = key.replace('topiclist_', 'vtl')
                    params[key] = value
            return params

        data = self._load(**kwargs)
        while data['roots']:
            for root in data['roots']:
                topic = Topic.from_topiclist_data(self, root, data)
                yield topic
            cont_args = _parse_url(data['links']['pagination'])
            data = self._load(**cont_args)


class Topic(FlowPage):

    """A Flow discussion topic."""

    def _load(self):
        """Load and cache the Topic's data."""
        if not hasattr(self, '_data'):
            self._data = self.site.load_topic(self)
        return self._data

    @classmethod
    def from_topiclist_data(cls, board, root_uuid, topiclist_data):
        """Create a Topic object from API data."""
        topic = cls(board.site, 'Topic:' + root_uuid)
        topic._root = Post.fromJSON(topic, root_uuid, topiclist_data)
        return topic

    @property
    def root(self):
        """The root post of this topic."""
        if not hasattr(self, '_root'):
            self._root = Post.fromJSON(self, self.uuid, self._data)
        return self._root

    def replies(self):
        """A list of replies to this topic."""
        return self.root.replies()


# Flow non-page-like objects
class Post(object):

    """A post to a Flow discussion topic."""

    def __init__(self, page, uuid):
        """
        Constructor.

        @param page: Flow topic
        @type page: Topic
        @param uuid: UUID of a Flow post
        @type uuid: unicode

        @raise TypeError: incorrect types of parameters
        @raise ValueError: use of non-Flow-enabled Site or invalid UUID
        """
        if not isinstance(page, Topic):
            raise TypeError('page must be a Topic object')

        if not uuid:
            raise ValueError('post UUID must be provided')

        self._page = page
        self._uuid = uuid

        self._content = {}

    @classmethod
    def fromJSON(cls, page, post_id, data):
        """
        Create a Post object using the data returned from the API call.

        @param page: A Flow topic
        @type page: Topic
        @param data: The JSON data returned from the API
        @type data: dict

        @return: A Post object
        """
        post = cls(page, post_id)
        post._set_data(data)

        return post

    def _set_data(self, data):
        """Set internal data and cache content."""
        self._data = data
        current_revision_id = data['posts'][self.uuid][0]
        self._current_revision = data['revisions'][current_revision_id]
        if 'content' in self._current_revision:
            content = self._current_revision.pop('content')
            self._content[content['format']] = content['content']

    def _load(self, format='wikitext'):
        """Load and cache the Post's data using the given content format."""
        data = self.site.load_post_current_revision(self.page, self.uuid, format)
        self._set_data(data)
        return self._data

    @property
    def uuid(self):
        """Return the UUID of the post.

        @return: UUID of the post
        @rtype: unicode
        """
        return self._uuid

    @property
    def site(self):
        """Return the site associated with the post.

        @return: Site associated with the post
        @rtype: Site
        """
        return self._page.site

    @property
    def page(self):
        """Return the page associated with the post.

        @return: Page associated with the post
        @rtype: FlowPage
        """
        return self._page

    def get(self, force=False, sysop=False, format='wikitext'):
        """Return the contents of the post in the given format.

        @param force: Whether to reload from the API instead of using the cache
        @type force: bool
        @param sysop: Whether to load using sysop rights. Implies force.
        @type sysop: bool
        @param format: Content format to return contents in
        @type format: unicode
        @return: The contents of the post in the given content format
        @rtype: unicode
        @raise NotImplementedError: use of 'sysop'
        """
        if sysop:
            raise NotImplementedError

        if format not in self._content or force:
            self._load(format)
        return self._content[format]

    def replies(self, format='wikitext', force=False):
        """Return this post's replies.

        @param format: Content format to return contents in
        @type format: unicode
        @param force: Whether to reload from the API instead of using the cache
        @type force: bool
        @return This post's replies
        @rtype: list of Posts
        """
        if hasattr(self, '_replies') and not force:
            return self._replies

        if not hasattr(self, '_current_revision') or force:
            self._load(format)

        reply_uuids = self._current_revision['replies']
        self._replies = [Post(self.page, id) for id in reply_uuids]

        return self._replies

# -*- coding: utf-8  -*-
"""Tests for the flow module."""
#
# (C) Pywikibot team, 2015
#
# Distributed under the terms of the MIT license.
#
from __future__ import unicode_literals

__version__ = '$Id$'

import pywikibot
import pywikibot.flow
import pywikibot.tools

from tests.aspects import (
    TestCase,
)

from tests.basepage_tests import (
    BasePageMethodsTestBase,
    BasePageLoadRevisionsCachingTestBase,
)

if not pywikibot.tools.PY2:
    unicode = str


class TestBoardBasePageMethods(BasePageMethodsTestBase):

    """Test Flow board pages using BasePage-defined methods."""

    family = 'mediawiki'
    code = 'mediawiki'

    def setUp(self):
        self._page = pywikibot.flow.Board(
            self.site, 'Talk:Sandbox')
        super(TestBoardBasePageMethods, self).setUp()

    def test_basepage_methods(self):
        """Test basic Page methods on a Flow board page."""
        self._test_invoke()
        self._test_return_datatypes()
        self.assertFalse(self._page.isRedirectPage())
        self.assertEqual(self._page.latest_revision.parent_id, 0)

    def test_content_model(self):
        """Test Flow page content model."""
        self.assertEqual(self._page.content_model, 'flow-board')


class TestTopicBasePageMethods(BasePageMethodsTestBase):

    """Test Flow topic pages using BasePage-defined methods."""

    family = 'mediawiki'
    code = 'mediawiki'

    def setUp(self):
        self._page = pywikibot.flow.Topic(
            self.site, 'Topic:Sh6wgo5tu3qui1w2')
        super(TestTopicBasePageMethods, self).setUp()

    def test_basepage_methods(self):
        """Test basic Page methods on a Flow topic page."""
        self._test_invoke()
        self._test_return_datatypes()
        self.assertFalse(self._page.isRedirectPage())
        self.assertEqual(self._page.latest_revision.parent_id, 0)

    def test_content_model(self):
        """Test Flow topic page content model."""
        self.assertEqual(self._page.content_model, 'flow-board')


class TestLoadRevisionsCaching(BasePageLoadRevisionsCachingTestBase):

    """Test site.loadrevisions() caching."""

    family = 'mediawiki'
    code = 'mediawiki'

    def setUp(self):
        self._page = pywikibot.flow.Board(
            self.site, 'Talk:Sandbox')
        super(TestLoadRevisionsCaching, self).setUp()

    def test_page_text(self):
        """Test site.loadrevisions() with Page.text."""
        self._test_page_text()


class TestFlowLoading(TestCase):

    """Test loading of Flow objects from the API."""

    family = 'mediawiki'
    code = 'mediawiki'

    cached = True

    def test_board_uuid(self):
        """Test retrieval of Flow board UUID."""
        site = self.get_site()
        board = pywikibot.flow.Board(site, 'Talk:Sandbox')
        self.assertEqual(board.uuid, 'rl7iby6wgksbpfno')

    def test_topic_uuid(self):
        """Test retrieval of Flow topic UUID."""
        site = self.get_site()
        topic = pywikibot.flow.Topic(site, 'Topic:Sh6wgo5tu3qui1w2')
        self.assertEqual(topic.uuid, 'sh6wgo5tu3qui1w2')

    def test_post_uuid(self):
        """Test retrieval of Flow post UUID.

        This doesn't really "load" anything from the API. It just tests
        the property to make sure the UUID passed to the constructor is
        stored properly.
        """
        site = self.get_site()
        topic = pywikibot.flow.Topic(site, 'Topic:Sh6wgo5tu3qui1w2')
        post = pywikibot.flow.Post(topic, 'sh6wgoagna97q0ia')
        self.assertEqual(post.uuid, 'sh6wgoagna97q0ia')

    def test_post_contents(self):
        """Test retrieval of Flow post contents."""
        # Load
        site = self.get_site()
        topic = pywikibot.flow.Topic(site, 'Topic:Sh6wgo5tu3qui1w2')
        post = pywikibot.flow.Post(topic, 'sh6wgoagna97q0ia')
        # Wikitext
        wikitext = post.get(format='wikitext')
        self.assertIn('wikitext', post._content)
        self.assertNotIn('html', post._content)
        self.assertIsInstance(wikitext, unicode)
        self.assertNotEqual(wikitext, '')
        # HTML
        html = post.get(format='html')
        self.assertIn('html', post._content)
        self.assertIn('wikitext', post._content)
        self.assertIsInstance(html, unicode)
        self.assertNotEqual(html, '')
        # Caching (hit)
        post._content['html'] = 'something'
        html = post.get(format='html')
        self.assertIsInstance(html, unicode)
        self.assertEqual(html, 'something')
        self.assertIn('html', post._content)
        # Caching (reload)
        post._content['html'] = 'something'
        html = post.get(format='html', force=True)
        self.assertIsInstance(html, unicode)
        self.assertNotEqual(html, 'something')
        self.assertIn('html', post._content)

    def test_topiclist(self):
        """Test loading of topiclist."""
        site = self.get_site()
        board = pywikibot.flow.Board(site, 'Talk:Sandbox')
        i = 0
        for topic in board.topics(limit=7):
            i += 1
            if i == 10:
                break
        self.assertEqual(i, 10)

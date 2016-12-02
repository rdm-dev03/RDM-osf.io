# -*- coding: utf-8 -*-
from nose.tools import *  # flake8: noqa

from api.base.settings.defaults import API_BASE

from tests.base import ApiTestCase
from tests.factories import (
    AuthUserFactory,
    PreprintFactory,
)


class PreprintCitationsMixin(object):

	def setUp(self):
		super(PreprintCitationsMixin, self).setUp()
		self.admin_contributor = AuthUserFactory()
		self.published_preprint = PreprintFactory(creator=self.admin_contributor)

	def test_unauthenticated_can_view_published_preprint_citations(self):
		res = self.app.get(self.published_preprint_url)
		assert_equal(res.status_code, 200)

	def test_preprint_citations_are_read_only(self):
		post_res = self.app.post_json_api(self.published_preprint_url, {}, auth=self.admin_contributor.auth, expect_errors=True)
		assert_equal(post_res.status_code, 405)
		put_res = self.app.put_json_api(self.published_preprint_url, {}, auth=self.admin_contributor.auth, expect_errors=True)
		assert_equal(put_res.status_code, 405)
		delete_res = self.app.delete_json_api(self.published_preprint_url, auth=self.admin_contributor.auth, expect_errors=True)
		assert_equal(delete_res.status_code, 405)


class TestPreprintCitations(PreprintCitationsMixin, ApiTestCase):

	def setUp(self):
		super(TestPreprintCitations, self).setUp()
		self.published_preprint_url = '/{}preprints/{}/citation/'.format(API_BASE, self.published_preprint._id)

	def test_citation_publisher_is_preprint_provider(self):
		res = self.app.get(self.published_preprint_url)
		assert_equal(res.status_code, 200)
		assert_equal(res.json['data']['attributes']['publisher'], self.published_preprint.provider.name)

	def test_citation_url_is_preprint_url_not_project(self):
		res = self.app.get(self.published_preprint_url)
		assert_equal(res.status_code, 200)
		assert_equal(res.json['data']['links']['self'], self.published_preprint.display_absolute_url)


class TestPreprintCitationsStyle(PreprintCitationsMixin, ApiTestCase):

	def setUp(self):
		super(TestPreprintCitationsStyle, self).setUp()
		self.published_preprint_url = '/{}preprints/{}/citation/apa/'.format(API_BASE, self.published_preprint._id)

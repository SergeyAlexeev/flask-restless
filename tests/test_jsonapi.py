"""
    tests.test_jsonapi
    ~~~~~~~~~~~~~~~~~~

    Provides tests ensuring that Flask-Restless meets the requirements of the
    `JSON API`_ standard.

    .. _JSON API: http://jsonapi.org

    :copyright: 2015 Jeffrey Finkelstein <jeffrey.finkelstein@gmail.com> and
                contributors.
    :license: GNU AGPLv3+ or BSD

"""
from urllib.parse import urlparse
from uuid import uuid1

from flask import json

from .helpers import TestSupport

loads = json.loads
dumps = json.dumps


class TestDocumentStructure(TestSupport):
    """Tests corresponding to the `Document Structure`_ section of the JSON API
    specification.

    .. _Document Structure: http://jsonapi.org/format/#document-structure-resource-relationships

    """

    def setUp(self):
        """Creates the database, the :class:`~flask.Flask` object, the
        :class:`~flask_restless.manager.APIManager` for that application, and
        creates the ReSTful API endpoints for the :class:`TestSupport.Person`
        and :class:`TestSupport.Computer` models.

        """
        # create the database
        super(TestDocumentStructure, self).setUp()

        # setup the URLs for the Person and Computer API
        self.manager.create_api(self.Person)
        self.manager.create_api(self.Computer)
        # HACK Need to create APIs for these other models because otherwise
        # we're not able to create the link URLs to them.
        self.manager.create_api(self.Project)
        self.manager.create_api(self.ComputerProgram)

    def test_get_primary_data(self):
        """Tests that the top-level key in a response is ``data``."""
        response = self.app.get('/api/person')
        assert response.status_code == 200
        assert 'data' in loads(response.data)

    def test_errors_top_level_key(self):
        """Tests that errors appear under a top-level key ``errors``."""
        response = self.app.get('/api/person/boguskey')
        data = loads(response.data)
        assert 'errors' in data

    def test_no_other_top_level_keys(self):
        """Tests that no there are no top-level keys in the response other than
        the allowed ones.

        """
        response = self.app.get('/api/person')
        data = loads(response.data)
        assert set(data) <= {'data', 'errors', 'links', 'linked', 'meta'}

    def test_resource_attributes(self):
        """Test that a resource has the required top-level keys."""
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        response = self.app.get('/api/person/1')
        person = loads(response.data)['data']
        assert person['id'] == '1'
        assert person['type'] == 'person'

    def test_self_link(self):
        """Tests that a request to a self link responds with the same object.

        For more information, see the `Resource URLs`_ section of the JSON API
        specification.

        .. _Resource URLs: http://jsonapi.org/format/#document-structure-resource-urls

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        response = self.app.get('/api/person/1')
        document1 = loads(response.data)
        person = document1['data']
        selfurl = person['links']['self']
        # The Flask test client doesn't need the `netloc` part of the URL.
        path = urlparse(selfurl).path
        response = self.app.get(path)
        document2 = loads(response.data)
        assert document1 == document2

    def test_self_relationship_url(self):
        """Tests that a link object correctly identifies its own relationship
        URL.

        For more information, see the `Resource Relationships`_ section of the
        JSON API specification.

        .. _Resource Relationships: http://jsonapi.org/format/#document-structure-resource-relationships

        """
        person = self.Person(id=1)
        computer = self.Computer(id=1)
        computer.owner = person
        self.session.add_all([person, computer])
        self.session.commit()
        response = self.app.get('/api/computer/1')
        computer = loads(response.data)['data']
        relationship_url = computer['links']['owner']['self']
        assert relationship_url.endswith('/api/computer/1/links/owner')

    def test_related_resource_url_to_one(self):
        """Tests that the related resource URL in a to-one relationship
        correctly identifies the related resource.

        For more information, see the `Resource Relationships`_ section of the
        JSON API specification.

        .. _Resource Relationships: http://jsonapi.org/format/#document-structure-resource-relationships

        """
        person = self.Person(id=1)
        computer = self.Computer(id=1)
        computer.owner = person
        self.session.add_all([person, computer])
        self.session.commit()
        # Get a resource that has links.
        response = self.app.get('/api/computer/1')
        computer = loads(response.data)['data']
        # Get the related resource URL.
        resource_url = computer['links']['owner']['resource']
        # The Flask test client doesn't need the `netloc` part of the URL.
        path = urlparse(resource_url).path
        # Fetch the resource at the related resource URL.
        response = self.app.get(path)
        document = loads(response.data)
        actual_person = document['data']
        # Compare it with what we expect to get.
        response = self.app.get('/api/person/1')
        expected_person = loads(response.data)['data']
        assert actual_person == expected_person

    def test_related_resource_url_to_many(self):
        """Tests that the related resource URL in a to-many relationship
        correctly identifies the related resource.

        For more information, see the `Resource Relationships`_ section of the
        JSON API specification.

        .. _Resource Relationships: http://jsonapi.org/format/#document-structure-resource-relationships

        """
        person = self.Person(id=1)
        computer = self.Computer(id=1)
        computer.owner = person
        self.session.add_all([person, computer])
        self.session.commit()
        # Get a resource that has links.
        response = self.app.get('/api/person/1')
        document = loads(response.data)
        person = document['data']
        # Get the related resource URL.
        resource_url = person['links']['computers']['resource']
        # The Flask test client doesn't need the `netloc` part of the URL.
        path = urlparse(resource_url).path
        # Fetch the resource at the related resource URL.
        response = self.app.get(path)
        document = loads(response.data)
        actual_computers = document['data']
        # Compare it with what we expect to get.
        #
        # TODO To make this test more robust, filter by `computer.owner == 1`.
        response = self.app.get('/api/computer')
        document = loads(response.data)
        expected_computers = document['data']
        assert actual_computers == expected_computers

    def test_link_object(self):
        """Tests for relations as resource URLs."""
        # TODO configure the api manager here
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        response = self.app.get('/api/person/1')
        person = loads(response.data)['data']
        computers = person['links']['computers']
        # A link object must contain at least one of 'self', 'resource',
        # linkage to a compound document, or 'meta'.
        assert computers['self'].endswith('/api/person/1/links/computers')
        assert computers['resource'].endswith('/api/person/1/computers')
        # TODO should also include pagination links

    def test_compound_document_to_many(self):
        """Tests for getting linked resources from a homogeneous to-many
        relationship in a compound document.

        For more information, see the `Compound Documents`_ section of the JSON
        API specification.

        .. _Compound Documents: http://jsonapi.org/format/#document-structure-compound-documents

        """
        person = self.Person(id=1)
        computer1 = self.Computer(id=1)
        computer2 = self.Computer(id=2)
        person.computers = [computer1, computer2]
        self.session.add_all([person, computer1, computer2])
        self.session.commit()
        # For a homogeneous to-many relationship, we should have a 'type' and
        # an 'ids' key.
        response = self.app.get('/api/person/1?include=computers')
        document = loads(response.data)
        person = document['data']
        computers = person['links']['computers']
        assert computers['type'] == 'computer'
        assert ['1', '2'] == sorted(computers['ids'])
        linked = document['linked']
        # Sort the links on their IDs, then get the two linked computers.
        linked_computer1, linked_computer2 = sorted(linked,
                                                    key=lambda c: c['id'])
        assert linked_computer1['type'] == 'computer'
        assert linked_computer1['id'] == '1'
        assert linked_computer2['type'] == 'computer'
        assert linked_computer2['id'] == '2'

    def test_compound_document_to_one(self):
        """Tests for getting linked resources from a to-one relationship in a
        compound document.

        For more information, see the `Compound Documents`_ section of the JSON
        API specification.

        .. _Compound Documents: http://jsonapi.org/format/#document-structure-compound-documents

        """
        person = self.Person(id=1)
        computer = self.Computer(id=1)
        computer.owner = person
        self.session.add_all([person, computer])
        self.session.commit()
        # For a to-one relationship, we should have a 'type' and an 'id' key.
        response = self.app.get('/api/computer/1?include=owner')
        document = loads(response.data)
        computer = document['data']
        owner = computer['links']['owner']
        assert owner['type'] == 'person'
        assert owner['id'] == 1
        linked = document['linked']
        linked_person = linked[0]
        assert linked_person['type'] == 'person'
        assert linked_person['id'] == '1'

    def test_compound_document_many_types(self):
        """Tests for getting linked resources of multiple types in a compound
        document.

        """
        # For example, get computers and projects of a person.
        assert False, 'Not implemented'

    def test_top_level_self_link(self):
        """Tests that there is a top-level links object containing a self link.

        For more information, see the `Top-level Link`_ section of the JSON API
        specification.

        .. _Top-level links: http://jsonapi.org/format/#document-structure-top-level-links

        """
        response = self.app.get('/api/person')
        document = loads(response.data)
        links = document['links']
        assert links['self'].endswith('/api/person')

    def test_top_level_pagination_link(self):
        """Tests that there are top-level pagination links by default.

        For more information, see the `Top-level Link`_ section of the JSON API
        specification.

        .. _Top-level links: http://jsonapi.org/format/#document-structure-top-level-links

        """
        response = self.app.get('/api/person')
        document = loads(response.data)
        links = document['links']
        assert 'first' in links
        assert 'last' in links
        assert 'prev' in links
        assert 'next' in links


class TestPagination(TestSupport):

    def setUp(self):
        super(TestPagination, self).setUp()
        self.manager.create_api(self.Person)
        # HACK Need to create APIs for these other models because otherwise
        # we're not able to create the link URLs to them.
        self.manager.create_api(self.Computer)
        self.manager.create_api(self.Project)
        #self.manager.create_api(self.ComputerProgram)

    def test_no_client_parameters(self):
        """Tests that a request without pagination query parameters returns the
        first page of the collection.

        For more information, see the `Pagination`_ section of the JSON API
        specification.

        .. _Pagination: http://jsonapi.org/format/#fetching-pagination

        """
        people = [self.Person() for i in range(25)]
        self.session.add_all(people)
        self.session.commit()
        response = self.app.get('/api/person')
        document = loads(response.data)
        pagination = document['links']
        assert pagination['first'] == 1
        assert pagination['last'] == 3
        assert pagination['prev'] == None
        assert pagination['next'] == 2
        assert len(document['data']) == 10

    def test_client_page_and_size(self):
        """Tests that a request that specifies both page number and page size
        returns the correct page of the collection.

        For more information, see the `Pagination`_ section of the JSON API
        specification.

        .. _Pagination: http://jsonapi.org/format/#fetching-pagination

        """
        people = [self.Person() for i in range(25)]
        self.session.add_all(people)
        self.session.commit()
        response = self.app.get('/api/person?page[number]=2&page[size]=3')
        document = loads(response.data)
        pagination = document['links']
        assert pagination['first'] == 1
        assert pagination['last'] == 9
        assert pagination['prev'] == 2
        assert pagination['next'] == 4
        assert len(document['data']) == 3

    def test_client_number_only(self):
        """Tests that a request that specifies only the page number returns the
        correct page with the default page size.

        For more information, see the `Pagination`_ section of the JSON API
        specification.

        .. _Pagination: http://jsonapi.org/format/#fetching-pagination

        """
        people = [self.Person() for i in range(25)]
        self.session.add_all(people)
        self.session.commit()
        response = self.app.get('/api/person?page[number]=2')
        document = loads(response.data)
        pagination = document['links']
        assert pagination['first'] == 1
        assert pagination['last'] == 3
        assert pagination['prev'] == 1
        assert pagination['next'] == 3
        assert len(document['data']) == 10

    def test_client_size_only(self):
        """Tests that a request that specifies only the page size returns the
        first page with the requested page size.

        For more information, see the `Pagination`_ section of the JSON API
        specification.

        .. _Pagination: http://jsonapi.org/format/#fetching-pagination

        """
        people = [self.Person() for i in range(25)]
        self.session.add_all(people)
        self.session.commit()
        response = self.app.get('/api/person?page[size]=5')
        document = loads(response.data)
        pagination = document['links']
        assert pagination['first'] == 1
        assert pagination['last'] == 5
        assert pagination['prev'] == None
        assert pagination['next'] == 2
        assert len(document['data']) == 5

    def test_short_page(self):
        """Tests that a request that specifies the last page may get fewer
        resources than the page size.

        For more information, see the `Pagination`_ section of the JSON API
        specification.

        .. _Pagination: http://jsonapi.org/format/#fetching-pagination

        """
        people = [self.Person() for i in range(25)]
        self.session.add_all(people)
        self.session.commit()
        response = self.app.get('/api/person?page[number]=3')
        document = loads(response.data)
        pagination = document['links']
        assert '/api/person?' in pagination['first']
        assert 'page[number]=1' in pagination['first']
        assert '/api/person?' in pagination['last']
        assert 'page[number]=3' in pagination['last']
        assert '/api/person?' in pagination['prev']
        assert 'page[number]=2' in pagination['prev']
        assert pagination['next'] == None
        assert len(document['data']) == 5

    def test_server_page_size(self):
        """Tests for setting the default page size on the server side.

        For more information, see the `Pagination`_ section of the JSON API
        specification.

        .. _Pagination: http://jsonapi.org/format/#fetching-pagination

        """
        people = [self.Person() for i in range(25)]
        self.session.add_all(people)
        self.session.commit()
        self.manager.create_api(self.Person, url_prefix='/api2', page_size=5)
        response = self.app.get('/api2/person?page[number]=3')
        document = loads(response.data)
        pagination = document['links']
        assert pagination['first'] == 1
        assert pagination['last'] == 5
        assert pagination['prev'] == 2
        assert pagination['next'] == 4
        assert len(document['data']) == 5

    def test_disable_pagination(self):
        """Tests for disabling default pagination on the server side.

        For more information, see the `Pagination`_ section of the JSON API
        specification.

        .. _Pagination: http://jsonapi.org/format/#fetching-pagination

        """
        people = [self.Person() for i in range(25)]
        self.session.add_all(people)
        self.session.commit()
        self.manager.create_api(self.Person, url_prefix='/api2', page_size=0)
        response = self.app.get('/api2/person')
        document = loads(response.data)
        pagination = document['links']
        assert 'first' not in pagination
        assert 'last' not in pagination
        assert 'prev' not in pagination
        assert 'next' not in pagination
        assert len(document['data']) == 25

    def test_disable_pagination_ignore_client(self):
        """Tests that disabling default pagination on the server side ignores
        client page number requests.

        For more information, see the `Pagination`_ section of the JSON API
        specification.

        .. _Pagination: http://jsonapi.org/format/#fetching-pagination

        """
        people = [self.Person() for i in range(25)]
        self.session.add_all(people)
        self.session.commit()
        self.manager.create_api(self.Person, url_prefix='/api2', page_size=0)
        response = self.app.get('/api2/person&page[number]=2')
        document = loads(response.data)
        pagination = document['links']
        assert 'first' not in pagination
        assert 'last' not in pagination
        assert 'prev' not in pagination
        assert 'next' not in pagination
        assert len(document['data']) == 25
        # TODO Should there be an error here?

    def test_max_page_size(self):
        """Tests that the client cannot exceed the maximum page size.

        For more information, see the `Pagination`_ section of the JSON API
        specification.

        .. _Pagination: http://jsonapi.org/format/#fetching-pagination

        """
        people = [self.Person() for i in range(25)]
        self.session.add_all(people)
        self.session.commit()
        self.manager.create_api(self.Person, url_prefix='/api2',
                                max_page_size=15)
        response = self.app.get('/api2/person?page[size]=20')
        document = loads(response.data)
        assert response.status_code == 400
        # TODO check the error message here.

    def test_negative_page_size(self):
        """Tests that the client cannot specify a negative page size.

        For more information, see the `Pagination`_ section of the JSON API
        specification.

        .. _Pagination: http://jsonapi.org/format/#fetching-pagination

        """
        response = self.app.get('/api/person?page[size]=-1')
        document = loads(response.data)
        assert response.status_code == 400
        # TODO check the error message here.

    def test_headers(self):
        """Tests that paginated requests come with ``Link`` headers.

        (This is not part of the JSON API standard, but should live with the
        other pagination test methods anyway.)

        """
        people = [self.Person() for i in range(25)]
        self.session.add_all(people)
        self.session.commit()
        response = self.app.get('/api/person?page[number]=4&page[size]=3')
        links = response.headers.getlist('Link')
        assert any('/api/person?page[number]=1&page[size]=3>; rel="first"' in l
                   for l in links)
        assert any('/api/person?page[number]=9&page[size]=3>; rel="last"' in l
                   for l in links)
        assert any('/api/person?page[number]=3&page[size]=3>; rel="prev"' in l
                   for l in links)
        assert any('/api/person?page[number]=5&page[size]=3>; rel="next"' in l
                   for l in links)


class TestFiltering(TestSupport):
    pass


class TestFetchingResources(TestSupport):
    """Tests corresponding to the `Fetching Resources`_ section of the JSON API
    specification.

    .. _Fetching Resources: http://jsonapi.org/format/#fetching

    """

    def setUp(self):
        """Creates the database, the :class:`~flask.Flask` object, the
        :class:`~flask_restless.manager.APIManager` for that application, and
        creates the ReSTful API endpoints for the :class:`TestSupport.Person`
        and :class:`TestSupport.Computer` models.

        """
        # create the database
        super(TestFetchingResources, self).setUp()

        # setup the URLs for the Person and Computer API
        self.manager.create_api(self.Person)
        self.manager.create_api(self.Computer)
        # HACK Need to create APIs for these other models because otherwise
        # we're not able to create the link URLs to them.
        self.manager.create_api(self.Project)
        self.manager.create_api(self.ComputerProgram)
        self.manager.create_api(self.Proof)

    def test_to_many(self):
        """Test for fetching resources from a to-many related resource URL."""
        person = self.Person(id=1)
        computer1 = self.Computer(id=1)
        computer2 = self.Computer(id=2)
        person.computers = [computer1, computer2]
        self.session.add_all([person, computer1, computer2])
        self.session.commit()
        response = self.app.get('/api/person/1/computers')
        assert response.status_code == 200
        document = loads(response.data)
        computers = document['data']
        assert ['1', '2'] == sorted(c['id'] for c in computers)

    def test_to_one(self):
        """Test for fetching resources from a to-one related resource URL."""
        person = self.Person(id=1)
        computer = self.Computer(id=1)
        computer.owner = person
        self.session.add_all([person, computer])
        self.session.commit()
        response = self.app.get('/api/computer/1/owner')
        document = loads(response.data)
        person = document['data']
        assert person['id'] == '1'

    def test_default_inclusion(self):
        """Tests that by default, Flask-Restless includes no information in
        compound documents.

        For more information, see the `Inclusion of Linked Resources`_ section
        of the JSON API specification.

        .. _Inclusion of Linked Resources: http://jsonapi.org/format/#fetching-includes

        """
        person = self.Person(id=1)
        computer = self.Computer(id=1)
        person.computers = [computer]
        self.session.add_all([person, computer])
        self.session.commit()
        # By default, no links will be included at the top level of the
        # document.
        response = self.app.get('/api/person/1')
        document = loads(response.data)
        person = document['data']
        computerids = person['links']['computers']['ids']
        assert computerids == ['1']
        assert 'linked' not in document

    def test_set_default_inclusion(self):
        """Tests that the user can specify default compound document
        inclusions when creating an API.

        For more information, see the `Inclusion of Linked Resources`_ section
        of the JSON API specification.

        .. _Inclusion of Linked Resources: http://jsonapi.org/format/#fetching-includes

        """
        person = self.Person(id=1)
        computer = self.Computer(id=1)
        person.computers = [computer]
        self.session.add_all([person, computer])
        self.session.commit()
        self.manager.create_api(self.Person, includes=['computers'],
                                url_prefix='/api2')
        # In the alternate API, computers are included by default in compound
        # documents.
        response = self.app.get('/api2/person/1')
        document = loads(response.data)
        person = document['data']
        linked = document['linked']
        computerids = person['links']['computers']['ids']
        assert computerids == ['1']
        assert linked[0]['type'] == 'computer'
        assert linked[0]['id'] == '1'

    def test_include(self):
        """Tests that the client can specify which linked relations to include
        in a compound document.

        For more information, see the `Inclusion of Linked Resources`_ section
        of the JSON API specification.

        .. _Inclusion of Linked Resources: http://jsonapi.org/format/#fetching-includes

        """
        person = self.Person(id=1, name='foo')
        computer1 = self.Computer(id=1)
        computer2 = self.Computer(id=2)
        project = self.Project()
        person.computers = [computer1, computer2]
        person.projects = [project]
        self.session.add_all([person, project, computer1, computer2])
        self.session.commit()
        response = self.app.get('/api/person/1?include=computers')
        assert response.status_code == 200
        document = loads(response.data)
        linked = document['linked']
        # If a client supplied an include request parameter, no other types of
        # objects should be included.
        assert all(c['type'] == 'computer' for c in linked)
        assert ['1', '2'] == sorted(c['id'] for c in linked)

    def test_include_multiple(self):
        """Tests that the client can specify multiple linked relations to
        include in a compound document.

        For more information, see the `Inclusion of Linked Resources`_ section
        of the JSON API specification.

        .. _Inclusion of Linked Resources: http://jsonapi.org/format/#fetching-includes

        """
        person = self.Person(id=1, name='foo')
        computer = self.Computer(id=2)
        project = self.Project(id=3)
        person.computers = [computer]
        person.projects = [project]
        self.session.add_all([person, project, computer])
        self.session.commit()
        response = self.app.get('/api/person/1?include=computers,projects')
        assert response.status_code == 200
        document = loads(response.data)
        # Sort the linked objects by type; 'computer' comes before 'project'
        # lexicographically.
        linked = sorted(document['linked'], key=lambda x: x['type'])
        linked_computer, linked_project = linked
        assert linked_computer['type'] == 'computer'
        assert linked_computer['id'] == '2'
        assert linked_project['type'] == 'project'
        assert linked_project['id'] == '3'

    def test_include_dot_separated(self):
        """Tests that the client can specify resources linked to other
        resources to include in a compound document.

        For more information, see the `Inclusion of Linked Resources`_ section
        of the JSON API specification.

        .. _Inclusion of Linked Resources: http://jsonapi.org/format/#fetching-includes

        """
        assert False, 'Not implemented'

    def test_sparse_fieldsets(self):
        """Tests that the client can specify which fields to return in the
        response of a fetch request for a single object.

        For more information, see the `Sparse Fieldsets`_ section
        of the JSON API specification.

        .. _Sparse Fieldsets: http://jsonapi.org/format/#fetching-sparse-fieldsets

        """
        person = self.Person(id=1, name='foo', age=99)
        self.session.add(person)
        self.session.commit()
        response = self.app.get('/api/person/1?fields[person]=id,name')
        document = loads(response.data)
        person = document['data']
        # ID and type must always be included.
        assert ['id', 'name', 'type'] == sorted(person)

    def test_sparse_fieldsets_id_and_type(self):
        """Tests that the ID and type of the resource are always included in a
        response from a request for sparse fieldsets, regardless of what the
        client requests.

        For more information, see the `Sparse Fieldsets`_ section
        of the JSON API specification.

        .. _Sparse Fieldsets: http://jsonapi.org/format/#fetching-sparse-fieldsets

        """
        person = self.Person(id=1, name='foo', age=99)
        self.session.add(person)
        self.session.commit()
        response = self.app.get('/api/person/1?fields[person]=id')
        document = loads(response.data)
        person = document['data']
        # ID and type must always be included.
        assert ['id', 'type'] == sorted(person)

    def test_sparse_fieldsets_collection(self):
        """Tests that the client can specify which fields to return in the
        response of a fetch request for a collection of objects.

        For more information, see the `Sparse Fieldsets`_ section
        of the JSON API specification.

        .. _Sparse Fieldsets: http://jsonapi.org/format/#fetching-sparse-fieldsets

        """
        person1 = self.Person(id=1, name='foo', age=99)
        person2 = self.Person(id=2, name='bar', age=80)
        self.session.add_all([person1, person2])
        self.session.commit()
        response = self.app.get('/api/person?fields[person]=id,name')
        document = loads(response.data)
        people = document['data']
        assert all(['id', 'name', 'type'] == sorted(p) for p in people)

    def test_sparse_fieldsets_multiple_types(self):
        """Tests that the client can specify which fields to return in the
        response with multiple types specified.

        For more information, see the `Sparse Fieldsets`_ section
        of the JSON API specification.

        .. _Sparse Fieldsets: http://jsonapi.org/format/#fetching-sparse-fieldsets

        """
        computer = self.Computer(id=1, name='bar')
        person = self.Person(id=1, name='foo', age=99, computers=[computer])
        self.session.add_all([person, computer])
        self.session.commit()
        # Person objects should only have ID and name, while computer objects
        # should only have ID.
        url = ('/api/person/1?include=computers'
               '&fields[person]=id,name,computers&fields[computer]=id')
        response = self.app.get(url)
        document = loads(response.data)
        person = document['data']
        linked = document['linked']
        # We requested 'id', 'name', and 'computers'; 'id' and 'type' must
        # always be present, and 'computers' comes under a 'links' key.
        assert ['id', 'links', 'name', 'type'] == sorted(person)
        assert ['computers'] == sorted(person['links'])
        # We requested only 'id', but 'type' must always appear as well.
        assert all(['id', 'type'] == sorted(computer) for computer in linked)

    def test_sort_increasing(self):
        """Tests that the client can specify the fields on which to sort the
        response in increasing order.

        For more information, see the `Sorting`_ section of the JSON API
        specification.

        .. _Sorting: http://jsonapi.org/format/#fetching-sorting

        """
        person1 = self.Person(name='foo', age=20)
        person2 = self.Person(name='bar', age=10)
        person3 = self.Person(name='baz', age=30)
        self.session.add_all([person1, person2, person3])
        self.session.commit()
        # The plus sign must be URL-encoded as ``%2B``.
        response = self.app.get('/api/person?sort=%2Bage')
        document = loads(response.data)
        people = document['data']
        age1, age2, age3 = (p['age'] for p in people)
        assert age1 <= age2 <= age3

    def test_sort_decreasing(self):
        """Tests that the client can specify the fields on which to sort the
        response in decreasing order.

        For more information, see the `Sorting`_ section of the JSON API
        specification.

        .. _Sorting: http://jsonapi.org/format/#fetching-sorting

        """
        person1 = self.Person(name='foo', age=20)
        person2 = self.Person(name='bar', age=10)
        person3 = self.Person(name='baz', age=30)
        self.session.add_all([person1, person2, person3])
        self.session.commit()
        response = self.app.get('/api/person?sort=-age')
        document = loads(response.data)
        people = document['data']
        age1, age2, age3 = (p['age'] for p in people)
        assert age1 >= age2 >= age3

    def test_sort_multiple_fields(self):
        """Tests that the client can sort by multiple fields.

        For more information, see the `Sorting`_ section of the JSON API
        specification.

        .. _Sorting: http://jsonapi.org/format/#fetching-sorting

        """
        person1 = self.Person(name='foo', age=99)
        person2 = self.Person(name='bar', age=99)
        person3 = self.Person(name='baz', age=80)
        person4 = self.Person(name='xyzzy', age=80)
        self.session.add_all([person1, person2, person3, person4])
        self.session.commit()
        # Sort by age, decreasing, then by name, increasing.
        #
        # The plus sign must be URL-encoded as ``%2B``.
        response = self.app.get('/api/person?sort=-age,%2Bname')
        document = loads(response.data)
        people = document['data']
        p1, p2, p3, p4 = people
        assert p1['age'] == p2['age'] >= p3['age'] == p4['age']
        assert p1['name'] <= p2['name']
        assert p3['name'] <= p4['name']

    def test_sort_relationship_attributes(self):
        """Tests that the client can sort by relationship attributes.

        For more information, see the `Sorting`_ section of the JSON API
        specification.

        .. _Sorting: http://jsonapi.org/format/#fetching-sorting

        """
        person1 = self.Person(age=20)
        person2 = self.Person(age=10)
        person3 = self.Person(age=30)
        computer1 = self.Computer(id=1, owner=person1)
        computer2 = self.Computer(id=2, owner=person2)
        computer3 = self.Computer(id=3, owner=person3)
        self.session.add_all([person1, person2, person3, computer1, computer2,
                              computer3])
        self.session.commit()
        # The plus sign must be URL-encoded as ``%2B``.
        response = self.app.get('/api/computer?sort=%2Bowner.age')
        document = loads(response.data)
        computers = document['data']
        assert ['2', '1', '3'] == [c['id'] for c in computers]

    def test_pagination(self):
        """Tests that the client receives pagination links.

        For more information, see the `Pagination`_ section of the JSON API
        specification.

        .. _Pagination: http://jsonapi.org/format/#fetching-pagination

        """
        assert False, 'Not implemented'

    def test_filtering(self):
        """Tests that the client can specify filters.

        For more information, see the `Filtering`_ section of the JSON API
        specification.

        .. _Filtering: http://jsonapi.org/format/#fetching-filtering

        """
        assert False, 'Not implemented'


class TestCreatingResources(TestSupport):
    """Tests corresponding to the `Creating Resources`_ section of the JSON API
    specification.

    .. _Creating Resources: http://jsonapi.org/format/#crud-creating

    """

    def setUp(self):
        """Creates the database, the :class:`~flask.Flask` object, the
        :class:`~flask_restless.manager.APIManager` for that application, and
        creates the ReSTful API endpoints for the :class:`TestSupport.Person`
        and :class:`TestSupport.Vehicle` models.

        """
        # create the database
        super(TestCreatingResources, self).setUp()

        # setup the URLs for the Person and Vehicle API
        self.manager.create_api(self.Person, methods=['POST'])
        self.manager.create_api(self.Vehicle, methods=['POST'],
                                allow_client_generated_ids=True)
        # HACK Need to create APIs for these other models because otherwise
        # we're not able to create the link URLs to them.
        self.manager.create_api(self.Computer)
        self.manager.create_api(self.Project)

    def test_create(self):
        """Tests that the client can create a single resource.

        For more information, see the `Creating Resources`_ section of the JSON
        API specification.

        .. _Creating Resources: http://jsonapi.org/format/#crud-creating

        """
        data = dict(data=dict(type='person', name='foo'))
        response = self.app.post('/api/person', data=dumps(data))
        assert response.status_code == 201
        location = response.headers['Location']
        # TODO Technically, this test shouldn't know beforehand where the
        # location of the created object will be. We are testing implementation
        # here, assuming that the implementation of the server creates a new
        # Person object with ID 1, which is bad style.
        assert location.endswith('/api/person/1')
        document = loads(response.data)
        person = document['data']
        assert person['type'] == 'person'
        assert person['id'] == '1'
        assert person['name'] == 'foo'
        assert person['links']['self'] == location

    def test_without_type(self):
        """Tests for an error response if the client fails to specify the type
        of the object to create.

        For more information, see the `Creating Resources`_ section of the JSON
        API specification.

        .. _Creating Resources: http://jsonapi.org/format/#crud-creating

        """
        data = dict(data=dict(name='foo'))
        response = self.app.post('/api/person', data=dumps(data))
        assert response.status_code == 400
        # TODO test for error details (for example, a message specifying that
        # type is missing)

    def test_client_generated_id(self):
        """Tests that the client can specify a UUID to become the ID of the
        created object.

        For more information, see the `Client-Generated IDs`_ section of the
        JSON API specification.

        .. _Client-Generated IDs: http://jsonapi.org/format/#crud-creating-client-ids

        """
        generated_id = uuid1()
        data = dict(data=dict(type='vehicle', id=generated_id))
        response = self.app.post('/api/vehicle', data=dumps(data))
        # Our server always responds with 201 when a client-generated ID is
        # specified. It does not return a 204.
        #
        # TODO should we reverse that and only return 204?
        assert response.status_code == 201
        document = loads(response.data)
        vehicle = document['data']
        assert vehicle['type'] == 'vehicle'
        assert vehicle['id'] == str(generated_id)

    def test_client_generated_id_forbidden(self):
        """Tests that the client can specify a UUID to become the ID of the
        created object.

        For more information, see the `Client-Generated IDs`_ section of the
        JSON API specification.

        .. _Client-Generated IDs: http://jsonapi.org/format/#crud-creating-client-ids

        """
        self.manager.create_api(self.Vehicle, url_prefix='/api2',
                                methods=['POST'])
        data = dict(data=dict(type='vehicle', id=uuid1()))
        response = self.app.post('/api2/vehicle', data=dumps(data))
        assert response.status_code == 403
        # TODO test for error details (for example, a message specifying that
        # client-generated IDs are not allowed).

    def test_type_conflict(self):
        """Tests that if a client specifies a type that does not match the
        endpoint, a :http:status:`409` is returned.

        For more information, see the `409 Conflict`_ section of the JSON API
        specification.

        .. _409 Conflict: http://jsonapi.org/format/#crud-creating-responses-409

        """

        data = dict(data=dict(type='bogustype', name='foo'))
        response = self.app.post('/api/person', data=dumps(data))
        assert response.status_code == 409
        # TODO test for error details (for example, a message specifying that
        # client-generated IDs are not allowed).

    def test_id_conflict(self):
        """Tests that if a client specifies a client-generated ID that already
        exists, a :http:status:`409` is returned.

        For more information, see the `409 Conflict`_ section of the JSON API
        specification.

        .. _409 Conflict: http://jsonapi.org/format/#crud-creating-responses-409

        """
        generated_id = uuid1()
        self.session.add(self.Vehicle(id=generated_id))
        self.session.commit()
        data = dict(data=dict(type='vehicle', id=generated_id))
        response = self.app.post('/api/vehicle', data=dumps(data))
        assert response.status_code == 409
        # TODO test for error details (for example, a message specifying that
        # client-generated IDs are not allowed).


class TestUpdatingResources(TestSupport):
    """Tests corresponding to the `Updating Resources`_ section of the JSON API
    specification.

    .. _Updating Resources: http://jsonapi.org/format/#crud-updating

    """

    def setUp(self):
        """Creates the database, the :class:`~flask.Flask` object, the
        :class:`~flask_restless.manager.APIManager` for that application, and
        creates the ReSTful API endpoints for the :class:`TestSupport.Person` and
        :class:`TestSupport.Computer` models.

        """
        # create the database
        super(TestUpdatingResources, self).setUp()

        # setup the URLs for the Person and Computer API
        self.manager.create_api(self.Person, methods=['PUT'])
        self.manager.create_api(self.Computer, methods=['PUT'])

    def test_update(self):
        """Tests that the client can update a resource's attributes.

        For more information, see the `Updating a Resource's Attributes`_
        section of the JSON API specification.

        .. _Updating a Resource's Attributes: http://jsonapi.org/format/#crud-updating-resource-attributes

        """
        person = self.Person(id=1, name='foo', age=10)
        self.session.add(person)
        self.session.commit()
        data = dict(data=dict(type='person', id='1', name='bar'))
        response = self.app.put('/api/person/1', data=dumps(data))
        assert response.status_code == 204
        assert person.id == 1
        assert person.name == 'bar'
        assert person.age == 10

    def test_to_one(self):
        """Tests that the client can update a resource's to-one relationships.

        For more information, see the `Updating a Resource's To-One Relationships`_
        section of the JSON API specification.

        .. _Updating a Resource's To-One Relationships: http://jsonapi.org/format/#crud-updating-resource-to-one-relationships

        """
        person1 = self.Person(id=1)
        person2 = self.Person(id=2)
        computer = self.Computer(id=1)
        person1.computers = [computer]
        self.session.add_all([person1, person2, computer])
        self.session.commit()
        # Change the owner of the computer from person 1 to person 2.
        data = {'data':
                    {'type': 'computer',
                     'id': '1',
                     'links':
                         {'owner':
                              {'type': 'person', 'id': '2'}
                          }
                     }
                }
        response = self.app.put('/api/computer/1', data=dumps(data))
        assert response.status_code == 204
        assert computer.owner is person2

    def test_remove_to_one(self):
        """Tests that the client can remove a resource's to-one relationship.

        For more information, see the `Updating a Resource's To-One Relationships`_
        section of the JSON API specification.

        .. _Updating a Resource's To-One Relationships: http://jsonapi.org/format/#crud-updating-resource-to-one-relationships

        """
        person = self.Person(id=1)
        computer = self.Computer()
        person.computers = [computer]
        self.session.add_all([person, computer])
        self.session.commit()
        # Change the owner of the computer to None.
        data = {'data':
                    {'type': 'computer',
                     'id': '1',
                     'links':
                         {'owner': None}
                     }
                }
        response = self.app.put('/api/computer/1', data=dumps(data))
        assert response.status_code == 204
        assert computer.owner is None

    def test_to_many(self):
        """Tests that the client can update a resource's to-many relationships.

        For more information, see the `Updating a Resource's To-Many Relationships`_
        section of the JSON API specification.

        .. _Updating a Resource's To-Many Relationships: http://jsonapi.org/format/#crud-updating-resource-to-many-relationships

        """
        person = self.Person(id=1)
        computer1 = self.Computer(id=1)
        computer2 = self.Computer(id=2)
        self.session.add_all([person, computer1, computer2])
        self.session.commit()
        self.manager.create_api(self.Person, methods=['PUT'],
                                url_prefix='/api2',
                                allow_to_many_replacement=True)
        data = {'data':
                    {'type': 'person',
                     'id': '1',
                     'links':
                         {'computers':
                              {'type': 'computer', 'ids': ['1', '2']}
                          }
                     }
                }
        response = self.app.put('/api2/person/1', data=dumps(data))
        assert response.status_code == 204
        assert set(person.computers) == {computer1, computer2}

    def test_to_many_clear(self):
        """Tests that the client can clear a resource's to-many relationships.

        For more information, see the `Updating a Resource's To-Many Relationships`_
        section of the JSON API specification.

        .. _Updating a Resource's To-Many Relationships: http://jsonapi.org/format/#crud-updating-resource-to-many-relationships

        """
        person = self.Person(id=1)
        computer1 = self.Computer(id=1)
        computer2 = self.Computer(id=2)
        person.computers = [computer1, computer2]
        self.session.add_all([person, computer1, computer2])
        self.session.commit()
        self.manager.create_api(self.Person, methods=['PUT'],
                                url_prefix='/api2',
                                allow_to_many_replacement=True)
        data = {'data':
                    {'type': 'person',
                     'id': '1',
                     'links':
                         {'computers':
                              {'type': 'computer', 'ids': []}
                          }
                     }
                }
        response = self.app.put('/api2/person/1', data=dumps(data))
        assert response.status_code == 204
        assert person.computers == []

    def test_to_many_forbidden(self):
        """Tests that the client receives a :http:status:`403` if the server
        has been configured to disallow full replacement of a to-many
        relationship.

        For more information, see the `Updating a Resource's To-Many Relationships`_
        section of the JSON API specification.

        .. _Updating a Resource's To-Many Relationships: http://jsonapi.org/format/#crud-updating-resource-to-many-relationships

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        data = {'data':
                    {'type': 'person',
                     'id': '1',
                     'links':
                         {'computers':
                              {'type': 'computer', 'ids': []}
                          }
                     }
                }
        response = self.app.put('/api/person/1', data=dumps(data))
        assert response.status_code == 403

    def test_other_modifications(self):
        """Tests that if an update causes additional changes in the resource in
        ways other than those specified by the client, the response has status
        :http:status:`200` and includes the updated resource.

        For more information, see the `200 OK`_ section of the JSON API
        specification.

        .. _200 OK: http://jsonapi.org/format/#crud-updating-responses-200

        """
        assert False, 'Not implemented'

    def test_nonexistent(self):
        """Tests that an attempt to update a nonexistent resource causes a
        :http:status:`404` response.

        For more information, see the `404 Not Found`_ section of the JSON API
        specification.

        .. _404 Not Found: http://jsonapi.org/format/#crud-updating-responses-404

        """
        data = dict(data=dict(type='person', id='1'))
        response = self.app.put('/api/person/1', data=dumps(data))
        assert response.status_code == 404

    def test_nonexistent_relationship(self):
        """Tests that an attempt to update a nonexistent resource causes a
        :http:status:`404` response.

        For more information, see the `404 Not Found`_ section of the JSON API
        specification.

        .. _404 Not Found: http://jsonapi.org/format/#crud-updating-responses-404

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        self.manager.create_api(self.Person, methods=['PUT'],
                                url_prefix='/api2',
                                allow_to_many_replacement=True)
        data = {'data':
                    {'type': 'person',
                     'id': '1',
                     'links':
                         {'computers':
                              {'type': 'computer', 'ids': [1]}
                          }
                     }
                }
        response = self.app.put('/api2/person/1', data=dumps(data))
        assert response.status_code == 404
        # TODO test for error details

    def test_conflicting_attributes(self):
        """Tests that an attempt to update a resource with a non-unique
        attribute value where uniqueness is required causes a
        :http:status:`409` response.

        For more information, see the `409 Conflict`_ section of the JSON API
        specification.

        .. _409 Conflict: http://jsonapi.org/format/#crud-updating-responses-409

        """
        person1 = self.Person(id=1, name='foo')
        person2 = self.Person(id=2)
        self.session.add_all([person1, person2])
        self.session.commit()
        data = dict(data=dict(type='person', id='2', name='foo'))
        response = self.app.put('/api/person/2', data=dumps(data))
        assert response.status_code == 409
        # TODO test for error details

    def test_conflicting_type(self):
        """Tests that an attempt to update a resource with the wrong type
        causes a :http:status:`409` response.

        For more information, see the `409 Conflict`_ section of the JSON API
        specification.

        .. _409 Conflict: http://jsonapi.org/format/#crud-updating-responses-409

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        data = dict(data=dict(type='bogus', id='1'))
        response = self.app.put('/api/person/1', data=dumps(data))
        assert response.status_code == 409
        # TODO test for error details

    def test_conflicting_id(self):
        """Tests that an attempt to update a resource with the wrong ID causes
        a :http:status:`409` response.

        For more information, see the `409 Conflict`_ section of the JSON API
        specification.

        .. _409 Conflict: http://jsonapi.org/format/#crud-updating-responses-409

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        data = dict(data=dict(type='person', id='bogus'))
        response = self.app.put('/api/person/1', data=dumps(data))
        assert response.status_code == 409
        # TODO test for error details


class TestUpdatingRelationships(TestSupport):
    """Tests corresponding to the `Updating Relationships`_ section of the JSON API
    specification.

    .. _Updating Relationships: http://jsonapi.org/format/#crud-updating-relationships

    """

    def setUp(self):
        """Creates the database, the :class:`~flask.Flask` object, the
        :class:`~flask_restless.manager.APIManager` for that application, and
        creates the ReSTful API endpoints for the :class:`TestSupport.Person` and
        :class:`TestSupport.Computer` models.

        """
        # create the database
        super(TestUpdatingRelationships, self).setUp()

        # setup the URLs for the Person and Computer API
        self.manager.create_api(self.Person, methods=['PUT', 'POST', 'DELETE'])
        self.manager.create_api(self.Computer, methods=['PUT'])

    def test_to_one(self):
        """Tests for updating a to-one relationship via a :http:method:`put`
        request to a relationship URL.

        For more information, see the `Updating To-One Relationships`_ section
        of the JSON API specification.

        .. _Updating To-One Relationships: http://jsonapi.org/format/#crud-updating-to-one-relationships

        """
        person1 = self.Person(id=1)
        person2 = self.Person(id=2)
        computer = self.Computer(id=1)
        computer.owner = person1
        self.session.add_all([person1, person2, computer])
        self.session.commit()
        data = dict(data=dict(type='person', id='2'))
        response = self.app.put('/api/computer/1/links/owner',
                                data=dumps(data))
        assert response.status_code == 204
        assert computer.owner is person2

    def test_remove_to_one(self):
        """Tests for removing a to-one relationship via a :http:method:`put`
        request to a relationship URL.

        For more information, see the `Updating To-One Relationships`_ section
        of the JSON API specification.

        .. _Updating To-One Relationships: http://jsonapi.org/format/#crud-updating-to-one-relationships

        """
        person1 = self.Person(id=1)
        person2 = self.Person(id=2)
        computer = self.Computer(id=1)
        computer.owner = person1
        self.session.add_all([person1, person2, computer])
        self.session.commit()
        data = dict(data=None)
        response = self.app.put('/api/computer/1/links/owner',
                                data=dumps(data))
        assert response.status_code == 204
        assert computer.owner is None

    def test_to_many(self):
        """Tests for replacing a to-many relationship via a :http:method:`put`
        request to a relationship URL.

        For more information, see the `Updating To-Many Relationships`_ section
        of the JSON API specification.

        .. _Updating To-Many Relationships: http://jsonapi.org/format/#crud-updating-to-many-relationships

        """
        person = self.Person(id=1)
        computer1 = self.Computer(id=1)
        computer2 = self.Computer(id=2)
        self.session.add_all([person, computer1, computer2])
        self.session.commit()
        self.manager.create_api(self.Person, methods=['PUT'],
                                url_prefix='/api2',
                                allow_to_many_replacement=True)
        data = dict(data=dict(type='computer', ids=['1', '2']))
        response = self.app.put('/api2/person/1/links/computers',
                                data=dumps(data))
        assert response.status_code == 204
        assert set(person.computers) == {computer1, computer2}

    def test_to_many_not_found(self):
        """Tests that an attempt to replace a to-many relationship with a
        related resource that does not exist yields an error response.

        For more information, see the `Updating To-Many Relationships`_ section
        of the JSON API specification.

        .. _Updating To-Many Relationships: http://jsonapi.org/format/#crud-updating-to-many-relationships

        """
        person = self.Person(id=1)
        computer = self.Computer(id=1)
        self.session.add_all([person, computer])
        self.session.commit()
        self.manager.create_api(self.Person, methods=['PUT'],
                                url_prefix='/api2',
                                allow_to_many_replacement=True)
        data = dict(data=dict(type='computer', ids=['1', '2']))
        response = self.app.put('/api2/person/1/links/computers',
                                data=dumps(data))
        assert response.status_code == 404
        # TODO test error messages

    def test_to_many_forbidden(self):
        """Tests that full replacement of a to-many relationship is forbidden
        by the server configuration, then the response is :http:status:`403`.

        For more information, see the `Updating To-Many Relationships`_ section
        of the JSON API specification.

        .. _Updating To-Many Relationships: http://jsonapi.org/format/#crud-updating-to-many-relationships

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        data = dict(data=dict(type='computer', ids=[]))
        response = self.app.put('/api/person/1/links/computers',
                                data=dumps(data))
        assert response.status_code == 403
        # TODO test error messages

    def test_to_many_append(self):
        """Tests for appending to a to-many relationship via a
        :http:method:`post` request to a relationship URL.

        For more information, see the `Updating To-Many Relationships`_ section
        of the JSON API specification.

        .. _Updating To-Many Relationships: http://jsonapi.org/format/#crud-updating-to-many-relationships

        """
        person = self.Person(id=1)
        computer1 = self.Computer(id=1)
        computer2 = self.Computer(id=2)
        self.session.add_all([person, computer1, computer2])
        self.session.commit()
        data = dict(data=dict(type='computer', ids=['1', '2']))
        response = self.app.post('/api/person/1/links/computers',
                                 data=dumps(data))
        assert response.status_code == 204
        assert set(person.computers) == {computer1, computer2}

    def test_to_many_preexisting(self):
        """Tests for attempting to append an element that already exists in a
        to-many relationship via a :http:method:`post` request to a
        relationship URL.

        For more information, see the `Updating To-Many Relationships`_ section
        of the JSON API specification.

        .. _Updating To-Many Relationships: http://jsonapi.org/format/#crud-updating-to-many-relationships

        """
        person = self.Person(id=1)
        computer = self.Computer(id=1)
        person.computers = [computer]
        self.session.add_all([person, computer])
        self.session.commit()
        data = dict(data=dict(type='computer', ids=['1']))
        response = self.app.post('/api/person/1/links/computers',
                                 data=dumps(data))
        assert response.status_code == 204
        assert person.computers == [computer]

    def test_to_many_delete(self):
        """Tests for deleting from a to-many relationship via a
        :http:method:`delete` request to a relationship URL.

        For more information, see the `Updating To-Many Relationships`_ section
        of the JSON API specification.

        .. _Updating To-Many Relationships: http://jsonapi.org/format/#crud-updating-to-many-relationships

        """
        person = self.Person(id=1)
        computer1 = self.Computer(id=1)
        computer2 = self.Computer(id=2)
        person.computers = [computer1, computer2]
        self.session.add_all([person, computer1, computer2])
        self.session.commit()
        self.manager.create_api(self.Person, methods=['DELETE'],
                                url_prefix='/api2',
                                allow_delete_from_to_many_relationships=True)
        data = dict(data=dict(type='computer', ids=['1']))
        response = self.app.delete('/api2/person/1/links/computers',
                                   data=dumps(data))
        assert response.status_code == 204
        assert person.computers == [computer2]

    def test_to_many_delete_nonexistent(self):
        """Tests for deleting a nonexistent member from a to-many relationship
        via a :http:method:`delete` request to a relationship URL.

        For more information, see the `Updating To-Many Relationships`_ section
        of the JSON API specification.

        .. _Updating To-Many Relationships: http://jsonapi.org/format/#crud-updating-to-many-relationships

        """
        person = self.Person(id=1)
        computer1 = self.Computer(id=1)
        computer2 = self.Computer(id=2)
        person.computers = [computer1]
        self.session.add_all([person, computer1, computer2])
        self.session.commit()
        self.manager.create_api(self.Person, methods=['DELETE'],
                                url_prefix='/api2',
                                allow_delete_from_to_many_relationships=True)
        data = dict(data=dict(type='computer', ids=['2']))
        response = self.app.delete('/api2/person/1/links/computers',
                                   data=dumps(data))
        assert response.status_code == 204
        assert person.computers == [computer1]

    def test_to_many_delete_forbidden(self):
        """Tests that attempting to delete from a to-many relationship via a
        :http:method:`delete` request to a relationship URL when the server has
        disallowed it yields a :http:status:`409` response.

        For more information, see the `Updating To-Many Relationships`_ section
        of the JSON API specification.

        .. _Updating To-Many Relationships: http://jsonapi.org/format/#crud-updating-to-many-relationships

        """
        person = self.Person(id=1)
        computer = self.Computer(id=1)
        person.computers = [computer]
        self.session.add_all([person, computer])
        self.session.commit()
        data = dict(data=dict(type='computer', ids=['1']))
        response = self.app.delete('/api/person/1/links/computers',
                                   data=dumps(data))
        assert response.status_code == 403
        assert person.computers == [computer]


class TestDeletingResources(TestSupport):
    """Tests corresponding to the `Deleting Resources`_ section of the JSON API
    specification.

    .. _Deleting Resources: http://jsonapi.org/format/#crud-deleting

    """

    def setUp(self):
        """Creates the database, the :class:`~flask.Flask` object, the
        :class:`~flask_restless.manager.APIManager` for that application, and
        creates the ReSTful API endpoints for the :class:`TestSupport.Person`
        class.

        """
        # create the database
        super(TestDeletingResources, self).setUp()
        self.manager.create_api(self.Person, methods=['DELETE'])

    def test_delete(self):
        """Tests for deleting a resource.

        For more information, see the `Deleting Resources`_ section of the JSON API
        specification.

        .. _Deleting Resources: http://jsonapi.org/format/#crud-deleting

        """
        person = self.Person(id=1)
        self.session.add(person)
        self.session.commit()
        response = self.app.delete('/api/person/1')
        assert response.status_code == 204
        assert self.session.query(self.Person).count() == 0

    def test_delete_nonexistent(self):
        """Tests that deleting a nonexistent resource causes a :http:status:`404`.

        For more information, see the `404 Not Found`_ section of the JSON API
        specification.

        .. _404 Not Found: http://jsonapi.org/format/#crud-deleting-responses-404

        """
        response = self.app.delete('/api/person/1')
        assert response.status_code == 404


# class TestJsonPatch(TestSupport):

#     def setUp(self):
#         """Creates the database, the :class:`~flask.Flask` object, the
#         :class:`~flask_restless.manager.APIManager` for that application, and
#         creates the ReSTful API endpoints for the :class:`testapp.Person` and
#         :class:`testapp.Computer` models.

#         """
#         # create the database
#         super(TestJsonAPI, self).setUp()

#         # setup the URLs for the Person and Computer API
#         self.manager.create_api(self.Person, methods=['PATCH'])
#         self.manager.create_api(self.Computer, methods=['PATCH'])

#     def test_json_patch_header(self):
#         self.session.add(self.Person())
#         self.session.commit()

#         # Requests must have the appropriate JSON Patch headers.
#         response = self.app.patch('/api/person/1',
#                                   content_type='application/vnd.api+json')
#         assert response.status_code == 400
#         response = self.app.patch('/api/person/1',
#                                   content_type='application/json')
#         assert response.status_code == 400

#     # TODO test bulk JSON Patch operations at the root level of the API.
#     def test_json_patch_create(self):
#         data = list(dict(op='add', path='/-', value=dict(name='foo')))
#         response = self.app.patch('/api/person', data=dumps(data))
#         assert response.status_code == 201
#         person = loads(response.data)
#         assert person['name'] == 'foo'

#     def test_json_patch_update(self):
#         person = self.Person(id=1, name='foo')
#         self.session.add(person)
#         self.session.commit()
#         data = list(dict(op='replace', path='/name', value='bar'))
#         response = self.app.patch('/api/person/1', data=dumps(data))
#         assert response.status_code == 204
#         assert person.name == 'bar'

#     def test_json_patch_to_one_relationship(self):
#         person1 = self.Person(id=1)
#         person2 = self.Person(id=2)
#         computer = self.Computer(id=1)
#         computer.owner = person1
#         self.session.add_all([person1, person2, computer])
#         self.session.commit()

#         # Change the owner of the computer from person 1 to person 2.
#         data = list(dict(op='replace', path='', value='2'))
#         response = self.app.patch('/api/computer/1/owner', data=dumps(data))
#         assert response.status_code == 204
#         assert computer.owner == person2

#     def test_json_patch_remove_to_one_relationship(self):
#         person = self.Person(id=1)
#         computer = self.Computer(id=1)
#         computer.owner = person
#         self.session.add_all([person, computer])
#         self.session.commit()

#         # Change the owner of the computer from person 1 to person 2.
#         data = list(dict(op='remove', path=''))
#         response = self.app.patch('/api/computer/1/owner', data=dumps(data))
#         assert response.status_code == 204
#         assert person.computers == []

#     def test_json_patch_to_many_relationship(self):
#         person = self.Person(id=1)
#         computer = self.Computer(id=1)
#         self.session.add_all([person, computer])
#         self.session.commit()

#         # Add computer 1 to the list of computers owned by person 1.
#         data = list(dict(op='add', path='/-', value='1'))
#         response = self.app.patch('/api/person/1/computers', data=dumps(data))
#         assert response.status_code == 204
#         assert person.computers == [computer]

#     def test_json_patch_remove_to_many_relationship(self):
#         person = self.Person(id=1)
#         computer = self.Computer(id=1)
#         person.computers = [computer]
#         self.session.add_all([person, computer])
#         self.session.commit()

#         # Remove computer 1 to the list of computers owned by person 1.
#         data = list(dict(op='remove', path='/1'))
#         response = self.app.patch('/api/person/1/computers', data=dumps(data))
#         assert response.status_code == 204
#         assert person.computers == []

#     def test_json_patch_delete(self):
#         person = self.Person(id=1)
#         self.session.add(person)
#         self.session.commit()

#         # Remove the person.
#         data = list(dict(op='remove', path=''))
#         response = self.app.patch('/api/person/1', data=dumps(data))
#         assert response.status_code == 204
#         assert self.Person.query.count() == 0

#     def test_json_patch_multiple(self):
#         # Create multiple person instances with a single request.
#         data = list(dict(op='add', path='/-', value=dict(name='foo')),
#                     dict(op='add', path='/-', value=dict(name='bar')))
#         response = self.app.patch('/api/person', data=dumps(data))
#         assert response.status_code == 200
#         assert response.content_type == 'application/json'
#         data = loads(response.data)
#         assert data[0]['person'][0]['name'] == 'foo'
#         assert data[1]['person'][0]['name'] == 'bar'

# class OldTests(TestSupport):

#     def setUp(self):
#         """Creates the database, the :class:`~flask.Flask` object, the
#         :class:`~flask_restless.manager.APIManager` for that application, and
#         creates the ReSTful API endpoints for the :class:`TestSupport.Person`
#         class.

#         """
#         super(OldTests, self).setUp()
#         #self.manager.create_api(...)

#     def test_get(self):
#         # Create a person object with multiple computers.
#         person1 = self.Person(id=1, name='foo')
#         person2 = self.Person(id=2, name='bar')
#         computer1 = self.Computer(id=1)
#         computer2 = self.Computer(id=2)
#         computer3 = self.Computer(id=3)
#         person1.computers = [computer1, computer2]
#         self.session.add_all([person1, person2])
#         self.session.add_all([computer1, computer2, computer3])
#         self.session.commit()

#         # Get the person and ensure all its data and one-to-many links are
#         # available.
#         response = self.app.get('/api/person/1')
#         assert response.status_code == 200
#         data = loads(response.data)
#         person = data['person']
#         assert person['id'] == '1'
#         assert person['name'] == 'foo'
#         computerids = person['links']['computers']
#         assert sorted(['1', '2']) == sorted(computerids)

#         # A person without any computers should have an empty list there.
#         response = self.app.get('/api/person/2')
#         assert response.status_code == 200
#         data = loads(response.data)
#         person = data['person']
#         assert person['id'] == '2'
#         assert person['name'] == 'bar'
#         assert [] == person['links']['computers']

#         # Get one of the computers and ensure that its many-to-one link is the
#         # ID of the person that owns it.
#         response = self.app.get('/api/computer/1')
#         assert response.status_code == 200
#         data = loads(response.data)
#         computer = data['computer']
#         assert computer['id'] == '1'
#         ownerid = computer['links']['owner']
#         assert '1' == ownerid

#         # A computer without an owner should have a null value there.
#         response = self.app.get('/api/computer/3')
#         assert response.status_code == 200
#         data = loads(response.data)
#         computer = data['computer']
#         assert computer['id'] == '3'
#         ownerid = computer['links']['owner']
#         assert None == ownerid

#     def test_resource_types(self):
#         """Tests that each resource has a type and an ID."""
#         self.session.add_all([self.Person(id=1), self.Computer(id=1)])
#         self.session.commit()
#         response = self.app.get('/api/person/1')
#         person = loads(response.data)['person']
#         assert person['id'] == '1'
#         assert person['type'] == 'person'
#         response = self.app.get('/api/computer/1')
#         person = loads(response.data)['computer']
#         assert person['id'] == '1'
#         assert person['type'] == 'computer'

#     def test_self_links(self):
#         person = self.Person(id=1)
#         self.session.add(person)
#         self.session.commit()
#         response = self.app.get('/api/person/1')
#         data = loads(response.data)
#         person = data['person']
#         assert person['links']['self'].endswith('/api/person/1')

#     def test_self_links_in_relationship(self):
#         person = self.Person(id=1)
#         computer = self.Computer(id=1)
#         person.computers = [computer]
#         self.session.add_all([person, computer])
#         self.session.commit()
#         response = self.app.get('/api/computer/1/links/owner')
#         data = loads(response.data)
#         person = data['person']
#         assert person['links']['self'].endswith('/api/person/1')

#     def test_top_level_links(self):
#         # Create a person object with multiple computers.
#         person = self.Person(id=1, name='foo')
#         computer1 = self.Computer(id=1)
#         computer2 = self.Computer(id=2)
#         person.computers = [computer1, computer2]
#         self.session.add_all([person, computer1, computer2])
#         self.session.commit()

#         # Check that the top-level document provides a link template to the
#         # links to the one-to-many relationships.
#         response = self.app.get('/api/person')
#         assert response.status_code == 200
#         data = loads(response.data)
#         # TODO Need to also test for `people.computers` if the collection name
#         # is specified by the user in `create_api()`.
#         template = data['links']['person.computers']
#         assert template.endswith('/api/person/{person.computers}')
#         # TODO Test for compound documents.

#     def test_get_multiple_with_commas(self):
#         person1 = self.Person(id=1)
#         person2 = self.Person(id=2)
#         self.session.add_all([person1, person2])
#         self.session.commit()

#         response = self.app.get('/api/person/1,2')
#         assert response.status_code == 200
#         data = loads(response.data)
#         assert sorted(['1', '2']) == sorted(p['id'] for p in data['person'])

#     def test_post_multiple(self):
#         data = dict(person=[dict(name='foo', age=10), dict(name='bar')])
#         response = self.app.post('/api/person', data=dumps(data))
#         assert response.status_code == 201
#         people = loads(response.data)['person']
#         assert sorted(['foo', 'bar']) == sorted(p['name'] for p in people)
#         # The server must respond with a Location header for each person.
#         #
#         # Sort the locations by primary key, which is the last character in the
#         # Location URL.
#         locations = sorted(response.headers.getlist('Location'),
#                            key=lambda s: s[-1])
#         assert locations[0].endswith('/api/person/1')
#         assert locations[1].endswith('/api/person/2')

#     def test_put_multiple(self):
#         person1 = self.Person(id=1, name='foo')
#         person2 = self.Person(id=2, age=99)
#         self.session.add_all([person1, person2])
#         self.session.commit()

#         # Updates a different field on each person.
#         data = dict(person=[dict(id=1, name='bar'), dict(id=2, age=10)])
#         response = self.app.put('/api/person/1,2', data=dumps(data))
#         assert response.status_code == 204
#         assert person1.name == 'bar'
#         assert person2.age == 10

#     def test_put_multiple_without_id(self):
#         person1 = self.Person(id=1, name='foo')
#         person2 = self.Person(id=2, age=99)
#         self.session.add_all([person1, person2])
#         self.session.commit()

#         # In order to avoid ambiguity, attempts to update multiple instances
#         # without specifying the ID in each object results in an error.
#         data = dict(person=[dict(name='bar'), dict(id=2, age=10)])
#         response = self.app.put('/api/person/1,2', data=dumps(data))
#         assert response.status_code == 400
#         # TODO Check the error message, description, etc.

#     def test_put_to_one_nonexistent(self):
#         person = self.Person(id=1)
#         computer = self.Computer(id=1)
#         self.session.add_all([person, computer])
#         self.session.commit()

#         # Set the owner of the computer to be the person with ID 1.
#         data = dict(person='1')
#         response = self.app.put('/api/computer/1/links/owner',
#                                 data=dumps(data))
#         assert response.status_code == 204
#         assert computer.owner is person

#     def test_post_to_one(self):
#         person = self.Person(id=1)
#         computer = self.Computer(id=1)
#         self.session.add_all([person, computer])
#         self.session.commit()

#         # Posting to a relationship URL should work if no link exists yet.
#         data = dict(person='1')
#         response = self.app.post('/api/computer/1/links/owner',
#                                  data=dumps(data))
#         assert response.status_code == 204

#     def test_post_to_one_exists(self):
#         person1 = self.Person(id=1)
#         person2 = self.Person(id=2)
#         computer = self.Computer(id=1)
#         person1.computers = [computer]
#         self.session.add_all([person1, person2, computer])
#         self.session.commit()

#         # Posting to a relationship URL should fail if a link already exists.
#         data = dict(person='1')
#         response = self.app.post('/api/computer/1/links/owner',
#                                  data=dumps(data))
#         assert response.status_code == 400
#         # TODO check the error message and description here.

#     def test_delete_to_one(self):
#         person = self.Person(id=1)
#         computer = self.Computer(id=1)
#         person.computers = [computer]
#         self.session.add_all([person, computer])
#         self.session.commit()

#         # Delete a relationship (without deleting the linked resource itself).
#         response = self.app.delete('/api/computer/1/links/owner')
#         assert response.status_code == 204

#     def test_delete_to_one_nonexistent(self):
#         computer = self.Computer(id=1)
#         self.session.add(computer)
#         self.session.commit()

#         # Attempting to delete a relationship that doesn't exist should fail.
#         response = self.app.delete('/api/computer/1/links/owner')
#         assert response.status_code == 400
#         # TODO check the error message and description here.

#     def test_post_to_many_relationship_url(self):
#         person = self.Person(id=1)
#         computer1 = self.Computer(id=1)
#         computer2 = self.Computer(id=2)
#         self.session.add_all([person, computer1, computer2])
#         self.session.commit()

#         # Add to the one-to-many relationship `computers` on a person instance.
#         data = dict(computers='1')
#         response = self.app.post('/api/person/1/links/computers',
#                                  data=dumps(data))
#         assert response.status_code == 204
#         assert computer1 in person.computers
#         assert computer2 not in person.computers

#     def test_post_to_many_relationship_url_multiple(self):
#         person = self.Person(id=1)
#         computer1 = self.Computer(id=1)
#         computer2 = self.Computer(id=2)
#         self.session.add_all([person, computer1, computer2])
#         self.session.commit()

#         # Add to the one-to-many relationship `computers` on a person instance.
#         data = dict(computers=['1', '2'])
#         response = self.app.post('/api/person/1/links/computers',
#                                  data=dumps(data))
#         assert response.status_code == 204
#         assert computer1 in person.computers
#         assert computer2 in person.computers

#     def test_post_already_exists(self):
#         person = self.Person(id=1)
#         self.session.add(person)
#         self.session.commit()

#         # Attempts to create a person that already exist return an error.
#         data = dict(person=dict(id=1))
#         response = self.app.post('/api/person', data=dumps(data))
#         assert response.status_code == 409  # Conflict

#     def test_delete_to_many(self):
#         person = self.Person(id=1)
#         computer1 = self.Computer(id=1)
#         computer2 = self.Computer(id=2)
#         person.computers = [computer1, computer2]
#         self.session.add_all([person, computer1, computer2])
#         self.session.commit()

#         # Delete from the the one-to-many relationship `computers` on a person
#         # instance.
#         response = self.app.delete('/api/person/1/links/computers/1')
#         assert response.status_code == 204
#         assert person.computers == [computer2]

#     def test_delete_to_many_multiple(self):
#         person = self.Person(id=1)
#         computer1 = self.Computer(id=1)
#         computer2 = self.Computer(id=2)
#         person.computers = [computer1, computer2]
#         self.session.add_all([person, computer1, computer2])
#         self.session.commit()

#         # Add to the one-to-many relationship `computers` on a person instance.
#         response = self.app.delete('/api/person/1/links/computers/1,2')
#         assert response.status_code == 204
#         assert person.computers == []

#     def test_put_nonexistent(self):
#         data = dict(name='bar')
#         response = self.app.put('/api/foo', data=dumps(data))
#         assert response.status_code == 404

#     def test_post_nonexistent_relationship(self):
#         data = dict(name='bar')
#         response = self.app.post('/api/person/1/links/foo', data=dumps(data))
#         assert response.status_code == 404

#     def test_delete_nonexistent_relationship(self):
#         response = self.app.delete('/api/person/1/links/foo')
#         assert response.status_code == 404

#     def test_delete_multiple(self):
#         person1 = self.Person(id=1)
#         person2 = self.Person(id=2)
#         self.session.add_all([person1, person2])
#         self.session.commit()

#         # Delete the person instances with IDs 1 and 2.
#         response = self.app.delete('/api/person/1,2')
#         assert response.status_code == 204
#         assert self.session.query(self.Person).count() == 0

#     def test_errors(self):
#         # TODO Test that errors are returned as described in JSON API docs.
#         pass

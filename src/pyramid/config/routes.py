import contextlib
from urllib.parse import urlparse
import warnings

from pyramid.config.actions import action_method
from pyramid.config.predicates import normalize_accept_offer, predvalseq
from pyramid.exceptions import ConfigurationError
from pyramid.interfaces import (
    PHASE2_CONFIG,
    IRequest,
    IRouteRequest,
    IRoutesMapper,
)
import pyramid.predicates
from pyramid.request import route_request_iface
from pyramid.urldispatch import RoutesMapper
from pyramid.util import as_sorted_tuple, is_nonstr_iter


class RoutesConfiguratorMixin:
    @action_method
    def add_route(
        self,
        name,
        pattern=None,
        factory=None,
        for_=None,
        header=None,
        xhr=None,
        accept=None,
        path_info=None,
        request_method=None,
        request_param=None,
        traverse=None,
        custom_predicates=(),
        use_global_views=False,
        path=None,
        pregenerator=None,
        static=False,
        inherit_slash=None,
        **predicates,
    ):
        """Add a :term:`route configuration` to the current configuration
        state.  Arguments to ``add_route`` are divided into *predicate*
        and *non-predicate* types.  :term:`Route predicate` arguments
        narrow the circumstances in which a route will match a
        request; non-predicate arguments are informational.

        Non-Predicate Arguments

        name

          The name of the route, e.g. ``myroute``.  This attribute is
          required.  It must be unique among all defined routes in a given
          application.

        factory

          A Python object (often a function or a class) or a :term:`dotted
          Python name` which refers to the same object that will generate a
          :app:`Pyramid` root resource object when this route matches. For
          example, ``mypackage.resources.MyFactory``.  If this argument is
          not specified, a default root factory will be used.  See
          :ref:`the_resource_tree` for more information about root factories.

        traverse

          If you would like to cause the :term:`context` to be
          something other than the :term:`root` object when this route
          matches, you can spell a traversal pattern as the
          ``traverse`` argument.  This traversal pattern will be used
          as the traversal path: traversal will begin at the root
          object implied by this route (either the global root, or the
          object returned by the ``factory`` associated with this
          route).

          The syntax of the ``traverse`` argument is the same as it is
          for ``pattern``. For example, if the ``pattern`` provided to
          ``add_route`` is ``articles/{article}/edit``, and the
          ``traverse`` argument provided to ``add_route`` is
          ``/{article}``, when a request comes in that causes the route
          to match in such a way that the ``article`` match value is
          ``'1'`` (when the request URI is ``/articles/1/edit``), the
          traversal path will be generated as ``/1``.  This means that
          the root object's ``__getitem__`` will be called with the
          name ``'1'`` during the traversal phase.  If the ``'1'`` object
          exists, it will become the :term:`context` of the request.
          :ref:`traversal_chapter` has more information about
          traversal.

          If the traversal path contains segment marker names which
          are not present in the ``pattern`` argument, a runtime error
          will occur.  The ``traverse`` pattern should not contain
          segment markers that do not exist in the ``pattern``
          argument.

          A similar combining of routing and traversal is available
          when a route is matched which contains a ``*traverse``
          remainder marker in its pattern (see
          :ref:`using_traverse_in_a_route_pattern`).  The ``traverse``
          argument to add_route allows you to associate route patterns
          with an arbitrary traversal path without using a
          ``*traverse`` remainder marker; instead you can use other
          match information.

          Note that the ``traverse`` argument to ``add_route`` is
          ignored when attached to a route that has a ``*traverse``
          remainder marker in its pattern.

        pregenerator

           This option should be a callable object that implements the
           :class:`pyramid.interfaces.IRoutePregenerator` interface.  A
           :term:`pregenerator` is a callable called by the
           :meth:`pyramid.request.Request.route_url` function to augment or
           replace the arguments it is passed when generating a URL for the
           route.  This is a feature not often used directly by applications,
           it is meant to be hooked by frameworks that use :app:`Pyramid` as
           a base.

        use_global_views

          When a request matches this route, and view lookup cannot
          find a view which has a ``route_name`` predicate argument
          that matches the route, try to fall back to using a view
          that otherwise matches the context, request, and view name
          (but which does not match the route_name predicate).

        static

          If ``static`` is ``True``, this route will never match an incoming
          request; it will only be useful for URL generation.  By default,
          ``static`` is ``False``.  See :ref:`static_route_narr`.

          .. versionadded:: 1.1

        inherit_slash

          This argument can only be used when the ``pattern`` is an empty
          string (``''``). By default, the composed route pattern will always
          include a trailing slash, but this argument provides a way to
          opt-out if both, you (the developer invoking ``add_route``) and the
          integrator (the developer setting the :term:`route prefix`),
          agree that the pattern should not contain a trailing slash.
          For example:

          .. code-block:: python

              with config.route_prefix_context('/users'):
                  config.add_route('users', '', inherit_slash=True)

          In this example, the resulting route pattern will be ``/users``.
          Alternatively, if the route prefix were ``/users/``, then the
          resulting route pattern would be ``/users/``.

          .. versionadded:: 2.0

        Predicate Arguments

        pattern

          The pattern of the route e.g. ``ideas/{idea}``.  This
          argument is required.  See :ref:`route_pattern_syntax`
          for information about the syntax of route patterns.  If the
          pattern doesn't match the current URL, route matching
          continues.

          .. note::

             For backwards compatibility purposes (as of :app:`Pyramid` 1.0), a
             ``path`` keyword argument passed to this function will be used to
             represent the pattern value if the ``pattern`` argument is
             ``None``.  If both ``path`` and ``pattern`` are passed,
             ``pattern`` wins.

        xhr

          This value should be either ``True`` or ``False``.  If this
          value is specified and is ``True``, the :term:`request` must
          possess an ``HTTP_X_REQUESTED_WITH`` (aka
          ``X-Requested-With``) header for this route to match.  This
          is useful for detecting AJAX requests issued from jQuery,
          Prototype and other Javascript libraries.  If this predicate
          returns ``False``, route matching continues.

        request_method

          A string representing an HTTP method name, e.g. ``GET``, ``POST``,
          ``HEAD``, ``DELETE``, ``PUT`` or a tuple of elements containing
          HTTP method names.  If this argument is not specified, this route
          will match if the request has *any* request method.  If this
          predicate returns ``False``, route matching continues.

          .. versionchanged:: 1.2
             The ability to pass a tuple of items as ``request_method``.
             Previous versions allowed only a string.

        path_info

          This value represents a regular expression pattern that will
          be tested against the ``PATH_INFO`` WSGI environment
          variable.  If the regex matches, this predicate will return
          ``True``.  If this predicate returns ``False``, route
          matching continues.

        request_param

          This value can be any string or an iterable of strings.  A view
          declaration with this argument ensures that the associated route will
          only match when the request has a key in the ``request.params``
          dictionary (an HTTP ``GET`` or ``POST`` variable) that has a
          name which matches the supplied value.  If the value
          supplied as the argument has a ``=`` sign in it,
          e.g. ``request_param="foo=123"``, then both the key
          (``foo``) must exist in the ``request.params`` dictionary, and
          the value must match the right hand side of the expression (``123``)
          for the route to "match" the current request.  If this predicate
          returns ``False``, route matching continues.

        header

          This argument can be a string or an iterable of strings for HTTP
          headers.  The matching is determined as follow:

          - If a string does not contain a ``:`` (colon), it will be
            considered to be the header name (example ``If-Modified-Since``).
            In this case, the header specified by the name must be present
            in the request for this string to match.  Case is not significant.

          - If a string contains a colon, it will be considered a
            name/value pair (for example ``User-Agent:Mozilla/.*`` or
            ``Host:localhost``), where the value part is a regular
            expression.  The header specified by the name must be present
            in the request *and* the regular expression specified as the
            value part must match the value of the request header.  Case is
            not significant for the header name, but it is for the value.

          All strings must be matched for this predicate to return ``True``.
          If this predicate returns ``False``, route matching continues.

        accept

          A :term:`media type` that will be matched against the ``Accept``
          HTTP request header.  If this value is specified, it may be a
          specific media type such as ``text/html``, or a list of the same.
          If the media type is acceptable by the ``Accept`` header of the
          request, or if the ``Accept`` header isn't set at all in the request,
          this predicate will match. If this does not match the ``Accept``
          header of the request, route matching continues.

          If ``accept`` is not specified, the ``HTTP_ACCEPT`` HTTP header is
          not taken into consideration when deciding whether or not to select
          the route.

          Unlike the ``accept`` argument to
          :meth:`pyramid.config.Configurator.add_view`, this value is
          strictly a predicate and supports :func:`pyramid.config.not_`.

          .. versionchanged:: 1.10

              Specifying a media range is deprecated due to changes in WebOb
              and ambiguities that occur when trying to match ranges against
              ranges in the ``Accept`` header. Support will be removed in
              :app:`Pyramid` 2.0. Use a list of specific media types to match
              more than one type.

          .. versionchanged:: 2.0

              Removed support for media ranges.

        is_authenticated

          This value, if specified, must be either ``True`` or ``False``.
          If it is specified and ``True``, only a request from an authenticated
          user, as determined by the :term:`security policy` in use, will
          satisfy the predicate.
          If it is specified and ``False``, only a request from a user who is
          not authenticated will satisfy the predicate.

          .. versionadded:: 2.0

        effective_principals

          If specified, this value should be a :term:`principal` identifier or
          a sequence of principal identifiers.  If the
          :attr:`pyramid.request.Request.effective_principals` property
          indicates that every principal named in the argument list is present
          in the current request, this predicate will return True; otherwise it
          will return False.  For example:
          ``effective_principals=pyramid.authorization.Authenticated`` or
          ``effective_principals=('fred', 'group:admins')``.

          .. versionadded:: 1.4a4

          .. deprecated:: 2.0
              Use ``is_authenticated`` or a custom predicate.

        custom_predicates

          .. deprecated:: 1.5
              This value should be a sequence of references to custom
              predicate callables.  Use custom predicates when no set of
              predefined predicates does what you need.  Custom predicates
              can be combined with predefined predicates as necessary.
              Each custom predicate callable should accept two arguments:
              ``info`` and ``request`` and should return either ``True``
              or ``False`` after doing arbitrary evaluation of the info
              and/or the request.  If all custom and non-custom predicate
              callables return ``True`` the associated route will be
              considered viable for a given request.  If any predicate
              callable returns ``False``, route matching continues.  Note
              that the value ``info`` passed to a custom route predicate
              is a dictionary containing matching information; see
              :ref:`custom_route_predicates` for more information about
              ``info``.

        \\*\\*predicates

          Pass extra keyword parameters to use custom predicates registered via
          :meth:`pyramid.config.Configurator.add_route_predicate`.  More than
          one custom predicate can be used at the same time.  See
          :ref:`view_and_route_predicates` for more information about
          custom predicates.

          .. versionadded:: 1.4

        """
        if custom_predicates:
            warnings.warn(
                (
                    'The "custom_predicates" argument to '
                    'Configurator.add_route is deprecated as of Pyramid 1.5. '
                    'Use "config.add_route_predicate" and use the registered '
                    'route predicate as a predicate argument to add_route '
                    'instead. See "Adding A Custom View, Route, or '
                    'Subscriber Predicate" in the "Hooks" chapter of the '
                    'documentation for more information.'
                ),
                DeprecationWarning,
                stacklevel=3,
            )

        if 'effective_principals' in predicates:
            warnings.warn(
                (
                    'The new security policy has deprecated '
                    'effective_principals. See "Upgrading '
                    'Authentication/Authorization" in "What\'s New in '
                    'Pyramid 2.0" of the documentation for more information.'
                ),
                DeprecationWarning,
                stacklevel=3,
            )

        if accept is not None:
            if not is_nonstr_iter(accept):
                accept = [accept]
            accept = [
                normalize_accept_offer(accept_option)
                for accept_option in accept
            ]

        # these are route predicates; if they do not match, the next route
        # in the routelist will be tried
        if request_method is not None:
            request_method = as_sorted_tuple(request_method)

        factory = self.maybe_dotted(factory)
        if pattern is None:
            pattern = path
        if pattern is None:
            raise ConfigurationError('"pattern" argument may not be None')

        if inherit_slash and pattern != '':
            raise ConfigurationError(
                '"inherit_slash" may only be used with an empty pattern'
            )

        # check for an external route; an external route is one which is
        # is a full url (e.g. 'http://example.com/{id}')
        parsed = urlparse(pattern)
        external_url = pattern

        if parsed.hostname:
            pattern = parsed.path

            original_pregenerator = pregenerator

            def external_url_pregenerator(request, elements, kw):
                if '_app_url' in kw:
                    raise ValueError(
                        'You cannot generate a path to an external route '
                        'pattern via request.route_path nor pass an _app_url '
                        'to request.route_url when generating a URL for an '
                        'external route pattern (pattern was "%s") '
                        % (pattern,)
                    )
                if '_scheme' in kw:
                    scheme = kw['_scheme']
                elif parsed.scheme:
                    scheme = parsed.scheme
                else:
                    scheme = request.scheme
                kw['_app_url'] = f'{scheme}://{parsed.netloc}'

                if original_pregenerator:
                    elements, kw = original_pregenerator(request, elements, kw)
                return elements, kw

            pregenerator = external_url_pregenerator
            static = True

        elif self.route_prefix:
            if pattern == '' and inherit_slash:
                pattern = self.route_prefix
            else:
                pattern = (
                    self.route_prefix.rstrip('/') + '/' + pattern.lstrip('/')
                )

        mapper = self.get_routes_mapper()

        introspectables = []

        intr = self.introspectable(
            'routes', name, f'{name} (pattern: {pattern!r})', 'route'
        )
        intr['name'] = name
        intr['pattern'] = pattern
        intr['factory'] = factory
        intr['xhr'] = xhr
        intr['request_methods'] = request_method
        intr['path_info'] = path_info
        intr['request_param'] = request_param
        intr['header'] = header
        intr['accept'] = accept
        intr['traverse'] = traverse
        intr['custom_predicates'] = custom_predicates
        intr['pregenerator'] = pregenerator
        intr['static'] = static
        intr['use_global_views'] = use_global_views

        if static is True:
            intr['external_url'] = external_url

        introspectables.append(intr)

        if factory:
            factory_intr = self.introspectable(
                'root factories',
                name,
                self.object_description(factory),
                'root factory',
            )
            factory_intr['factory'] = factory
            factory_intr['route_name'] = name
            factory_intr.relate('routes', name)
            introspectables.append(factory_intr)

        def register_route_request_iface():
            request_iface = self.registry.queryUtility(
                IRouteRequest, name=name
            )
            if request_iface is None:
                if use_global_views:
                    bases = (IRequest,)
                else:
                    bases = ()
                request_iface = route_request_iface(name, bases)
                self.registry.registerUtility(
                    request_iface, IRouteRequest, name=name
                )

        def register_connect():
            pvals = predicates.copy()
            pvals.update(
                dict(
                    xhr=xhr,
                    request_method=request_method,
                    path_info=path_info,
                    request_param=request_param,
                    header=header,
                    accept=accept,
                    traverse=traverse,
                    custom=predvalseq(custom_predicates),
                )
            )

            predlist = self.get_predlist('route')
            _, preds, _ = predlist.make(self, **pvals)
            route = mapper.connect(
                name,
                pattern,
                factory,
                predicates=preds,
                pregenerator=pregenerator,
                static=static,
            )
            intr['object'] = route
            return route

        # We have to connect routes in the order they were provided;
        # we can't use a phase to do that, because when the actions are
        # sorted, actions in the same phase lose relative ordering
        self.action(('route-connect', name), register_connect)

        # But IRouteRequest interfaces must be registered before we begin to
        # process view registrations (in phase 3)
        self.action(
            ('route', name),
            register_route_request_iface,
            order=PHASE2_CONFIG,
            introspectables=introspectables,
        )

    @action_method
    def add_route_predicate(
        self, name, factory, weighs_more_than=None, weighs_less_than=None
    ):
        """Adds a route predicate factory.  The view predicate can later be
        named as a keyword argument to
        :meth:`pyramid.config.Configurator.add_route`.

        ``name`` should be the name of the predicate.  It must be a valid
        Python identifier (it will be used as a keyword argument to
        ``add_route``).

        ``factory`` should be a :term:`predicate factory` or :term:`dotted
        Python name` which refers to a predicate factory.

        See :ref:`view_and_route_predicates` for more information.

        .. versionadded:: 1.4
        """
        self._add_predicate(
            'route',
            name,
            factory,
            weighs_more_than=weighs_more_than,
            weighs_less_than=weighs_less_than,
        )

    def add_default_route_predicates(self):
        p = pyramid.predicates
        for (name, factory) in (
            ('xhr', p.XHRPredicate),
            ('request_method', p.RequestMethodPredicate),
            ('path_info', p.PathInfoPredicate),
            ('request_param', p.RequestParamPredicate),
            ('header', p.HeaderPredicate),
            ('accept', p.AcceptPredicate),
            ('is_authenticated', p.IsAuthenticatedPredicate),
            ('effective_principals', p.EffectivePrincipalsPredicate),
            ('custom', p.CustomPredicate),
            ('traverse', p.TraversePredicate),
        ):
            self.add_route_predicate(name, factory)

    def get_routes_mapper(self):
        """Return the :term:`routes mapper` object associated with
        this configurator's :term:`registry`."""
        mapper = self.registry.queryUtility(IRoutesMapper)
        if mapper is None:
            mapper = RoutesMapper()
            self.registry.registerUtility(mapper, IRoutesMapper)
        return mapper

    @contextlib.contextmanager
    def route_prefix_context(self, route_prefix):
        """
        Return this configurator with a :term:`route prefix` temporarily set.

        When the context exits, the ``route_prefix`` is reset to the original.

        ``route_prefix`` is a string suitable to be used as a route prefix,
        or ``None``.

        Example Usage:

        .. code-block:: python

            config = Configurator()
            with config.route_prefix_context('foo'):
                config.add_route('bar', '/bar')

        .. versionadded:: 1.10

        """
        original_route_prefix = self.route_prefix

        if route_prefix is None:
            route_prefix = ''

        old_route_prefix = self.route_prefix
        if old_route_prefix is None:
            old_route_prefix = ''

        route_prefix = '{}/{}'.format(
            old_route_prefix.rstrip('/'), route_prefix.lstrip('/')
        )

        route_prefix = route_prefix.strip('/')

        if not route_prefix:
            route_prefix = None

        self.begin()
        try:
            self.route_prefix = route_prefix
            yield

        finally:
            self.route_prefix = original_route_prefix
            self.end()

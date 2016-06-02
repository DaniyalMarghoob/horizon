# Copyright (C) 2016 Universidad Politecnica de Madrid
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging

from horizon import forms
from horizon import messages
from horizon import exceptions

from django.forms import ValidationError
from django import shortcuts
from django.core.urlresolvers import reverse_lazy

from openstack_dashboard.fiware_api import keystone

LOG = logging.getLogger('idm_logger')


class UpdateEndpointsForm(forms.SelfHandlingForm):
    action = reverse_lazy('horizon:endpoints_management:endpoints_management:index')
    description = 'Account status'
    template_name = 'endpoints_management/endpoints_management/_endpoints.html'

    def __init__(self, *args, **kwargs):
        self.services = kwargs.pop('services')
        self.endpoints = kwargs.pop('endpoints')

        super(UpdateEndpointsForm, self).__init__(*args, **kwargs)

        fields = {}
        initial = {}

        # add fields for existing endpoints, and set initial values
        for endpoint in self.endpoints:
            service_name = ''.join(service.name for service in self.services \
                if service.id == endpoint.service_id)
            fields[endpoint.id] = forms.CharField(label=service_name + '_' + endpoint.interface,
                                                  required=False,
                                                  widget=forms.TextInput(
                                                    attrs={'data-service-name': service_name,
                                                            'data-endpoint-interface': endpoint.interface
                                                          }))
            initial[endpoint.id] = endpoint.url

        # add blank fields for new service, if any
        new_service = None
        if 'new_service_name' in self.request.session:
            new_service = self.request.session['new_service_name']
            fields['new_service'] = forms.CharField(required=False,
                                                     widget=forms.HiddenInput())
            initial['new_service'] = new_service

        elif 'new_service' in self.request.POST:
            new_service = self.request.POST.get('new_service')
        
        if new_service:
            for interface in ['public', 'admin', 'internal']:
                fields[new_service + '_' + interface] = forms.CharField(label=new_service + '_' + interface,
                                                                        required=False,
                                                                        widget=forms.TextInput(
                                                                        attrs={'data-service-name': new_service,
                                                                               'data-endpoint-interface': interface
                                                                        }))

        self.fields = fields
        self.initial = initial

    def clean(self):
        cleaned_data = super(UpdateEndpointsForm, self).clean()
        new_data = {}

        # endpoints may arrive in any order, so we need to count them in order 
        # to check if all of them are empty (delete service) or just some of 
        # them (validation error)

        empty_services = []
        empty_endpoints = []

        for endpoint_id, new_url in cleaned_data.iteritems():
            endpoint = keystone.endpoint_get(self.request, endpoint_id)
            if new_url == u'':
                empty_services.append(endpoint.service_id if endpoint else endpoint_id.split('_')[0])

        for service_id in set(empty_services):
            if empty_services.count(service_id) < 3:
                service = keystone.service_get(self.request, service_id)
                raise ValidationError(('All interfaces for {0} service must be provided'.format(
                    service.name.capitalize() if service else service_id.capitalize())))

        # save endpoints to be deleted when handling form
        self.empty_endpoints = [e for e, url in cleaned_data.iteritems() if url == u'' ]
            
        return new_data

    def handle(self, request, data):

        new_services = set()
        updated_services = set()
        deleted_services = set()

        # create and update endpoints
        for endpoint_id, new_url in data.iteritems():
            endpoint = keystone.endpoint_get(request, endpoint_id)
            import pdb; pdb.set_trace()
            if '_' in endpoint_id: # new endpoint ID will look like "service_interface"
                service_name, interface = endpoint_id.split('_')
                service = next((s for s in self.services if s.name == service_name), None)
                if not service:
                    LOG.debug ('Service {0} is not created, skipping this endpoint'.format(service_name))
                    messages.error(request, 
                        'Unable to store {0} endpoint for {1} service (service not found).'.format(interface, service_name))
                    continue
                keystone.endpoint_create(request, service=service, url=new_url, interface=interface, region=request.session['endpoints_region'])
                new_services.add(service_name)

            # existing endpoint ID can be used to retrieve endpoint object
            elif new_url != '' and new_url != endpoint.url: 
                service = keystone.service_get(request, endpoint.service_id)
                service_name = service.name
                keystone.endpoint_update(request, endpoint_id=endpoint_id, endpoint_new_url=new_url)
                updated_services.add(service_name)

        self._delete_empty_endpoints(request)
        self._create_endpoint_group_for_region(request)

        # display success messages
        if len(new_services) > 0:
            messages.success(request, 'Service{0} {1} {2} enabled for your region.'
                .format('' if len(new_services) == 0 else 's',
                        ', '.join([s.capitalize() for s in new_services]),
                        'was' if len(new_services) == 0 else 'were'))
        if len(updated_services) > 0:
            messages.success(request, 'Service{0} {1} {2} updated.'
                .format('' if len(updated_services) == 0 else 's',
                        ', '.join([s.capitalize() for s in updated_services]),
                        'was' if len(updated_services) == 0 else 'were'))

        return shortcuts.redirect('horizon:endpoints_management:endpoints_management:index')

    def _delete_empty_endpoints(self, request):
        if getattr(self, 'empty_endpoints'):
            for endpoint_id in self.empty_endpoints:
                keystone.endpoint_delete(request, endpoint_id)
            messages.success(request, 'Blank endpoints deleted.')

    def _create_endpoint_group_for_region(self, request):
        endpoint_group_for_region = [
            eg for eg in keystone.endpoint_group_list(request)
            if eg.filters.get('region_id', None) == request.session['endpoints_region']
        ]

        if not endpoint_group_for_region:
            LOG.debug('Creating endpoint_group for region {0}'.format(request.session['endpoints_region']))
            keystone.endpoint_group_create(
                request=request,
                name=request.session['endpoints_region'] + ' Region Group',
                region_id=request.session['endpoints_region'])


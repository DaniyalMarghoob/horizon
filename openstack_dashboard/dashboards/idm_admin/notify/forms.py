# Copyright (C) 2014 Universidad Politecnica de Madrid
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

from django import forms
from django.core import mail
from django.template.loader import render_to_string

from django_summernote.widgets import SummernoteWidget

from horizon import exceptions
from horizon import forms
from horizon import messages

from openstack_dashboard import api


LOG = logging.getLogger('idm_logger')

class EmailForm(forms.SelfHandlingForm):
    subject = forms.CharField(max_length=50,
                                label=("Subject"),
                                required=True)
    body = forms.CharField(widget=SummernoteWidget(),
                                label=("Body"),
                                required=True)

    # TODO(garcianavalon) as settings
    EMAIL_HTML_TEMPLATE = 'email/base_email.html'
    EMAIL_TEXT_TEMPLATE = 'email/base_email.txt'
    def handle(self, request, data):
        # TODO(garcianavalon) better email architecture...
        try:

            all_users = [u.name for u in api.keystone.user_list(request)
                if hasattr(u, 'name')]

            text_content = render_to_string(self.EMAIL_TEXT_TEMPLATE, 
                dictionary={
                    'massive_footer':True,
                    'content': data['body'],
                })
            html_content = render_to_string(self.EMAIL_HTML_TEMPLATE, 
                dictionary={
                    'massive_footer':True,
                    'content': data['body'],
                })

            connection = mail.get_connection(fail_silently=True)

            msg = mail.EmailMultiAlternatives(data['subject'], text_content, 
                'no-reply@account.lab.fi-ware.org', all_users, connection=connection)
            msg.attach_alternative(html_content, "text/html")
            msg.send()

            messages.success(request, ('Message sent succesfully.'))

        except Exception:
            msg = ('Unable to send message. Please try again later.')
            LOG.warning(msg)
            exceptions.handle(request, msg)
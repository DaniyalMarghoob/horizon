# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from django.conf.urls import patterns
from django.conf.urls import url

from openstack_auth import views as openstack_auth_views

from openstack_dashboard.fiware_auth import forms as fiware_auth_forms
from openstack_dashboard.fiware_auth import views


urlpatterns = patterns(
    'fiware_auth.views',
    url(r"^sign_up/$", views.RegistrationView.as_view(), 
                            name='fiware_auth_register'),
    url(r'^activate/$', views.ActivationView.as_view(),
                            name='fiware_auth_activate'),
    url(r'^password/request/$', views.RequestPasswordResetView.as_view(),
                            name='fiware_auth_request'),
    url(r'^password/reset/$', views.ResetPasswordView.as_view(),
                            name='fiware_auth_reset'),
    url(r'^confirmation/$', views.ResendConfirmationInstructionsView.as_view(),
                            name='fiware_auth_confirmation'),
    # NOTE(garcianavalon) override to use our form
    url(r'^auth/login/$', openstack_auth_views.login, 
        {'form_class': fiware_auth_forms.LoginWithEmailForm}, name='login'),
    # NOTE(garcianavalon) override to add a message
    url(r'^auth/switch/(?P<tenant_id>[^/]+)/$', views.switch, name='switch_tenants'),
)
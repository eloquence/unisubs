from django import forms
from django.core.exceptions import SuspiciousOperation
from django.utils.translation import ugettext_lazy as _

from icanhaz.models import VideoVisibilityPolicy

class VideoVisibilityForm(forms.Form):

    site_visibility_policy = forms.ChoiceField(
            choices=VideoVisibilityPolicy.SITE_VISIBILITY_POLICIES)
    owner = forms.ChoiceField()

    widget_visibility_policy = forms.ChoiceField(
            choices=VideoVisibilityPolicy.WIDGET_VISIBILITY_POLICIES)
    #owner = forms.ChoiceField(choices=None)
    

    def __init__(self,  *args, **kwargs):
        self.user = kwargs.pop("user")
        self.video = kwargs.pop("video")
        super(VideoVisibilityForm, self).__init__(*args, **kwargs)
        self.fields["owner"].choices = (("user-%s" % self.user.pk, _("Only me"),), ) 
        [("team-%s" % x.pk, "Team %s" % x.name) for  x in self.user.managed_teams()]
    
    def clean_owner(self):
        """
        Make sure this hasn't been tampered with. we only accept
        the initial owner or one of the teams he's a manager of.
        """
        raw =  self.cleaned_data.get('owner', None)
        if raw is None:
            return None
        model_name, pk = raw.split("-")
        if model_name == "user":
            owner = self.user
        else:
            owner = user.managed_teams.get(pk=pk)
        return owner

    def is_valid(self, *args, **kwargs):
        if not VideoVisibilityPolicy.objects.can_create_for_video(self.video, self.user):
            raise SuspiciousOperation(_("This user cannot change those settings"))
        return super(VideoVisibilityForm, self).is_valid(*args, **kwargs)

# Amara, universalsubtitles.org
#
# Copyright (C) 2013 Participatory Culture Foundation
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see
# http://www.gnu.org/licenses/agpl-3.0.html.

"""externalsites.syncing.youtube -- Sync subtitles to/from Youtube"""

from __future__ import absolute_import
import logging

from django.conf import settings
from django.utils import translation
import babelsubs
import unilangs

from utils.metrics import Meter, Occurrence
from .. import google

# NOTE
# It would be nice to use API version 3 for this and also to use the
# externalsites.google module to handle it.  However, captions are currently
# only supported on version 2 -- even though its deprecated.  So this is
# basically code copied from the old videos.types.youtube module and it uses
# the version 2 client library.

AMARA_CREDIT = translation.ugettext_lazy("Subtitles by the Amara.org community")
AMARA_DESCRIPTON_CREDIT = translation.ugettext_lazy(
    "Help us caption & translate this video!")

logger = logging.getLogger("externalsites.syncing.youtube")

CAPTION_TRACK_LINK_REL = ('http://gdata.youtube.com'
                          '/schemas/2007#video.captionTracks')

def _format_subs_for_youtube(subtitle_set):
    return babelsubs.to(subtitle_set, 'vtt').encode('utf-8')

def get_youtube_language_code(language_code):
    """Convert the language for a SubtitleVersion to a youtube code
    """
    lc = unilangs.LanguageCode(language_code.lower(), "unisubs")
    return lc.encode("youtube")

def find_existing_caption_id(access_token, video_id, language_code):
    for caption_info in google.captions_list(access_token, video_id):
        if language_code == caption_info[1] and caption_info[2] == '':
            return caption_info[0]
    return None

def update_subtitles(video_id, access_token, subtitle_version):
    """Push the subtitles for a language to YouTube """

    try:
        language_code = get_youtube_language_code(
            subtitle_version.subtitle_language.language_code)
    except KeyError:
        logger.error("Couldn't encode LC %s to youtube" % language_code)
        return

    subs = subtitle_version.get_subtitles()
    if should_add_credit_to_subtitles(subtitle_version, subs):
        add_credit_to_subtitles(subtitle_version, subs)
    content = _format_subs_for_youtube(subs)

    caption_id = find_existing_caption_id(access_token, video_id,
                                          language_code)
    if caption_id:
        google.captions_update(access_token, caption_id, 'text/vtt', content)
    else:
        google.captions_insert(access_token, video_id, language_code,
                               'text/vtt', content)

def delete_subtitles(video_id, access_token, language_code):
    """Delete the subtitles for a language on YouTube """

    caption_id = find_existing_caption_id(access_token, video_id,
                                          language_code)
    if caption_id:
        google.captions_delete(access_token, caption_id)

def should_add_credit_to_subtitles(subtitle_version, subs):
    if len(subs) == 0 or not subs.fully_synced:
        return False
    if subtitle_version.video.get_team_video() is not None:
        return False
    if not subtitle_version.video.duration:
        return False
    return True

def add_credit_to_subtitles(subtitle_version, subs):
    with translation.override(subtitle_version.language_code):
        credit_text = translation.gettext(AMARA_CREDIT)

    duration = subtitle_version.video.duration * 1000

    last_sub = subs[-1]
    if last_sub.end_time is None or last_sub.end_time >= duration:
        return

    start_time = max(last_sub.end_time, duration - 3000)
    subs.append_subtitle(start_time, duration, credit_text)

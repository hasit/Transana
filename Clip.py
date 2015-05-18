# Copyright (C) 2003 - 2005 The Board of Regents of the University of Wisconsin System 
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#

"""This module implements the Clip class as part of the Data Objects."""

__author__ = 'Nathaniel Case, David Woods <dwoods@wcer.wisc.edu>'

import wx
from DataObject import *
from DBInterface import *
from TransanaExceptions import *
import Episode
import ClipKeywordObject
import Collection
import Transcript
import Note
# Import the Transana Constants
import TransanaConstants
# Import Transana's Global Variables
import TransanaGlobal
import types

TIMECODE_CHAR = "\\'a4"   # Note that this differs from the TIMECODE_CHAR in TranscriptEditor.py
                          # because this is for RTF text and that is for parsed text.

class Clip(DataObject):
    """This class defines the structure for a clip object.  A clip object
    describes a portion of a video (or other media) file."""

    def __init__(self, id_or_num=None, collection_name=None, collection_parent=0):
        """Initialize an Clip object."""
        DataObject.__init__(self)
        # By default, use the Video Root folder if one has been defined
        self.useVideoRoot = (TransanaGlobal.configData.videoPath != '')

        if type(id_or_num) in (int, long):
            self.db_load_by_num(id_or_num)
        elif isinstance(id_or_num, types.StringTypes):
            self.db_load_by_name(id_or_num, collection_name, collection_parent)
        else:
            self.number = 0
            self.id = ''
            self.comment = ''
            self.collection_num = 0
            self.collection_id = ''
            self.episode_num = 0
            # TranscriptNum is the Transcript Number the Clip was created FROM, not the number of the Clip Transcript!
            self.transcript_num = 0
            self.clip_transcript_num = 0
            self.media_filename = 0
            self.clip_start = 0
            self.clip_stop = 0
            self.sort_order = 0
            
        # Create empty placeholders for Series and Episode IDs.  These only get populated if the
        # values are needed, and cannot be implemented in the regular LOADs because the Series/
        # Episode may no longer exist.
        self._series_id = ""
        self._episode_id = ""


# Public methods
    def __repr__(self):
        str = 'Clip Object Definition:\n'
        str = str + "number = %s\n" % self.number
        str = str + "id = %s\n" % self.id
        str = str + "comment = %s\n" % self.comment
        str = str + "collection_num = %s\n" % self.collection_num 
        str = str + "collection_id = %s\n" % self.collection_id
        str = str + "episode_num = %s\n" % self.episode_num
        # TranscriptNum is the Transcript Number the Clip was created FROM, not the number of the Clip Transcript!
        str = str + "Originating transcript_num = %s\n" % self.transcript_num
        str = str + "clip_transcript_num = %s\n" % self.clip_transcript_num
        str = str + "media_filename = %s\n" % self.media_filename 
        str = str + "clip_start = %s\n" % self.clip_start
        str = str + "clip_stop = %s\n" % self.clip_stop
        str = str + "sort_order = %s\n" % self.sort_order
        for kws in self.keyword_list:
            str = str + "Keyword:  %s\n" % kws
        str = str + '\n'
        return str
        
    def GetTranscriptWithoutTimeCodes(self):
        """ Returns a copy of the Transcript Text with the Time Code information removed. """
        newText = self.text
        while True:
            timeCodeStart = newText.find(TIMECODE_CHAR)
            if timeCodeStart == -1:
                break
            timeCodeEnd = newText.find('>', timeCodeStart)

            # print newText[timeCodeStart:timeCodeEnd+1]
            
            newText = newText[:timeCodeStart] + newText[timeCodeEnd + 1:]

        # We should also replace TAB characters with spaces        
        while True:
            tabStart = newText.find(chr(wx.WXK_TAB), 0)
            if tabStart == -1:
                break
            newText = newText[:tabStart] + '  ' + newText[tabStart + 1:]

        return newText

    def db_load_by_name(self, clip_name, collection_name, collection_parent=0):
        """Load a record by ID / Name."""
        db = DBInterface.get_db()
        query = """
        SELECT a.*, b.*, c.TranscriptNum ClipTranscriptNum, c.RTFText
          FROM Clips2 a, Collections2 b, Transcripts2 c
          WHERE ClipID = %s AND
                a.CollectNum = b.CollectNum AND
                b.CollectID = %s AND
                b.ParentCollectNum = %s AND
                c.TranscriptID = "" AND
                a.ClipNum = c.ClipNum
        """
        c = db.cursor()
        c.execute(query, (clip_name, collection_name, collection_parent))
        n = c.rowcount
        if (n != 1):
            c.close()
            self.clear()
            raise RecordNotFoundError, (collection_name + ", " + clip_name, n)
        else:
            r = DBInterface.fetch_named(c)
            self._load_row(r)
            self.refresh_keywords()
            
        c.close()
        
    def db_load_by_num(self, num):
        """Load a record by record number."""
        db = DBInterface.get_db()
        query = """
        SELECT a.*, b.*, c.TranscriptNum ClipTranscriptNum, c.RTFText
          FROM Clips2 a, Collections2 b, Transcripts2 c
          WHERE a.ClipNum = %s AND
                a.CollectNum = b.CollectNum AND
                c.TranscriptID = "" AND
                a.ClipNum = c.ClipNum
        """
        c = db.cursor()
        c.execute(query, (num,))
        n = c.rowcount
        if (n != 1):
            c.close()
            self.clear()
            raise RecordNotFoundError, (num, n)
        else:
            r = DBInterface.fetch_named(c)
            self._load_row(r)
            self.refresh_keywords()

        c.close()

    def db_save(self):
        """Save the record to the database using Insert or Update as
        appropriate."""

        # Sanity checks
        if self.id == "":
            raise SaveError, _("Clip ID is required.")
        if (self.collection_num == 0):
            raise SaveError, _("Parent Collection number is required.")
        # If the transcript that a Clip was created from is deleted, you can have a Clip without a Transcript Number.
        # Legacy Data may also have no Transcript Number.
        # elif (self.transcript_num == 0):
            # raise SaveError, "No Transcript number"
        elif self.media_filename == "":
            raise SaveError, _("Media Filename is required.")
        else:
            # Create a string of legal characters for the file names
            allowedChars = TransanaConstants.legalFilenameCharacters
            # check each character in the file name string
            for char in self.media_filename:
                # If the character is illegal ...
                if allowedChars.find(char) == -1:
                    msg = _('There is an unsupported character in the Media File Name.\n\n"%s" includes the "%s" character, which Transana does not allow at this time.\nPlease rename your folders and files so that they do not include characters that are not part of US English.\nWe apologize for this inconvenience.') % (self.media_filename, char)
                    raise SaveError, msg

        self._sync_collection()

        # Determine if we are supposed to extract the Video Root Path from the Media Filename and extract it if appropriate
        if self.useVideoRoot and (TransanaGlobal.configData.videoPath == self.media_filename[:len(TransanaGlobal.configData.videoPath)]):
            tempMediaFilename = self.media_filename[len(TransanaGlobal.configData.videoPath):]
        else:
            tempMediaFilename = self.media_filename

        values = (self.id, self.collection_num, self.episode_num, \
                      self.transcript_num, tempMediaFilename, \
                      self.clip_start, self.clip_stop, self.comment, \
                      self.sort_order)
        if (self._db_start_save() == 0):
            if DBInterface.record_match_count("Clips2", \
                                ("ClipID", "CollectNum"), \
                                (self.id, self.collection_num) ) > 0:
                raise SaveError, _('A Clip named "%s" already exists in this Collection.\nPlease enter a different Clip ID.') % self.id
            # insert the new record
            query = """
            INSERT INTO Clips2
                (ClipID, CollectNum, EpisodeNum, TranscriptNum,
                 MediaFile, ClipStart, ClipStop, ClipComment,
                 SortOrder)
                VALUES
                (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """
        else:
            if DBInterface.record_match_count("Clips2", \
                            ("ClipID", "CollectNum", "!ClipNum"), \
                            (self.id, self.collection_num, self.number)) > 0:
                raise SaveError, _('A Clip named "%s" already exists in this Collection.\nPlease enter a different Clip ID.') % self.id

            # update the record
            query = """
            UPDATE Clips2
                SET ClipID = %s,
                    CollectNum = %s,
                    EpisodeNum = %s,
                    TranscriptNum = %s,
                    MediaFile = %s,
                    ClipStart = %s,
                    ClipStop = %s,
                    ClipComment = %s,
                    SortOrder = %s
                WHERE ClipNum = %s
            """
            values = values + (self.number,)
        
        c = DBInterface.get_db().cursor()
        c.execute(query, values)
        if self.number == 0:
            # If we are dealing with a brand new Clip, it does not yet know its
            # record number.  It HAS a record number, but it is not known yet.
            # The following query should produce the correct record number.
            query = """
                      SELECT ClipNum FROM Clips2
                      WHERE ClipID = %s AND
                            CollectNum = %s
                    """
            tempDBCursor = DBInterface.get_db().cursor()
            tempDBCursor.execute(query, (self.id, self.collection_num))
            if tempDBCursor.rowcount == 1:
                self.number = tempDBCursor.fetchone()[0]
            else:
                raise RecordNotFoundError, (self.id, tempDBCursor.rowcount)
            tempDBCursor.close()
        else:
            # If we are dealing with an existing Clip, delete all the Keywords
            # in anticipation of putting them all back in after we deal with the
            # Clip Transcript
            DBInterface.delete_all_keywords_for_a_group(0, self.number)
        # Now let's deal with the Clip's Transcript
        if self.clip_transcript_num == 0:
            # Create a Transcript Object for the Transcript data
            tempTranscript = Transcript.Transcript()
            # Assign the data that needs to be saved
            tempTranscript.episode_num = self.episode_num
            tempTranscript.clip_num = self.number
            tempTranscript.text = self.text
            # Save the new Transcript record
            tempTranscript.db_save()
            # Now we need to assign the Transcript Object's new Record Number to the
            # Clip Object.  First, let's reload the Transcript Object so it knows it's
            # record number
            tempTranscript = Transcript.Transcript(clip = self.number)
            # Now that the Transcript Object knows its record number, assign it to the Clip Object
            self.clip_transcript_num = tempTranscript.number
            
        elif self.clip_transcript_num > 0:
            # Load the existing Transcript Record
            tempTranscript = Transcript.Transcript(clip=self.number)
            # Lock the Transcript record
            tempTranscript.lock_record()
            # Update the Transcript Data
            tempTranscript.text = self.text
            # Save the new Transcript record
            tempTranscript.db_save()
            # unlock the Transcript Record
            tempTranscript.unlock_record()
        # Add the Episode keywords back
        for kws in self._kwlist:
            DBInterface.insert_clip_keyword(0, self.number, kws.keywordGroup, kws.keyword, kws.example)
        c.close()

    def db_delete(self, use_transactions=1):
        """Delete this object record from the database."""
        # Initialize delete operation, begin transaction if necessary
        (db, c) = self._db_start_delete(use_transactions)
        result = 1

        # If this clip serves as a Keyword Example, we should prompt the user about
        # whether it should really be deleted
        kwExampleList = DBInterface.list_all_keyword_examples_for_a_clip(self.number)
        if len(kwExampleList) > 0:
            if len(kwExampleList) == 1:
                prompt = _('Clip "%s" has been defined as a Keyword Example for Keyword "%s : %s".') % (self.id, kwExampleList[0][0], kwExampleList[0][1])
            else:
                prompt = _('Clip "%s" has been defined as a Keyword Example for multiple Keywords.') % self.id
            prompt = prompt + '\nAre you sure you want to delete it?'
            dlg = wx.MessageDialog(None, prompt, _('Delete Clip'), wx.YES_NO | wx.CENTRE | wx.ICON_QUESTION | wx.STAY_ON_TOP)
            if dlg.ShowModal() == wx.ID_NO:
                dlg.Destroy()
                return 0
            else:
                dlg.Destroy()
        
        # Detect, Load, and Delete all Clip Notes.
        notes = self.get_note_nums()
        for note_num in notes:
            note = Note.Note(note_num)
            result = result and note.db_delete(0)
            del note
        del notes

        trans = Transcript.Transcript(clip=self.number)
        # if transcript delete fails, rollback clip delete
        result = result and trans.db_delete(0)
        del trans

        # NOTE:  It is important for the calling routine to delete references to the Keyword Examples
        #        from the screen.  However, that code does not belong in the Clip Object, but in the
        #        user interface.  That is why it is not included here as part of the result.

        # Delete all related references in the ClipKeywords table
        if result:
            DBInterface.delete_all_keywords_for_a_group(0, self.number)

        # Delete the actual record.
        self._db_do_delete(use_transactions, c, result)

        # Cleanup
        c.close()
        self.clear()

        return result

    def duplicate(self):
        # Inherit duplicate method
        newClip = DataObject.duplicate(self)
        # A new Clip should get a new Clip Transcript!
        newClip.clip_transcript_num = 0
        # Sort Order should not be duplicated!
        newClip.sort_order = 0
        # Copying a Clip should not cause additional Keyword Examples to be created.
        # We need to strip the "example" status for all keywords in the new clip.
        for clipKeyword in newClip.keyword_list:
            clipKeyword.example = 0
        return newClip
        
    def clear_keywords(self):
        """Clear the keyword list."""
        self._kwlist = []
        
    def refresh_keywords(self):
        """Clear the keyword list and refresh it from the database."""
        self._kwlist = []
        kwpairs = DBInterface.list_of_keywords(Clip=self.number)
        for data in kwpairs:
            tempClipKeyword = ClipKeywordObject.ClipKeyword(data[0], data[1], clipNum=self.number, example=data[2])
            self._kwlist.append(tempClipKeyword)
        
    def add_keyword(self, kwg, kw):
        """Add a keyword to the keyword list."""
        # We need to check to see if the keyword is already in the keyword list
        keywordFound = False
        # Iterate through the list
        for clipKeyword in self._kwlist:
            # If we find a match, set the flag and quit looking.
            if (clipKeyword.keywordGroup == kwg) and (clipKeyword.keyword == kw):
                keywordFound = True
                break

        # If the keyword is not found, add it.  (If it's already there, we don't need to do anything!)
        if not keywordFound:
            # Create an appropriate ClipKeyword Object
            tempClipKeyword = ClipKeywordObject.ClipKeyword(kwg, kw, clipNum=self.number)
            # Add it to the Keyword List
            self._kwlist.append(tempClipKeyword)

    def remove_keyword(self, kwg, kw):
        """Remove a keyword from the keyword list.  The value returned by this function can be:
             0  Keyword NOT deleted.  (probably overridden by the user)
             1  Keyword deleted, but it was NOT a Keyword Example
             2  Keyword deleted, and it WAS a Keyword Example. """
        # We need different return codes for failure, success of a Non-Example, and success of an Example.
        # If it's an example, we need to remove the Node on the Database Tree Tab

        # Let's assume the Delete will fail (or be refused by the user) until it actually happens.
        delResult = 0

        # We need to find the keyword in the keyword list
        # Iterate through the keyword list
        for index in range(len(self._kwlist)):

            # Look for the entry to be deleted
            if (self._kwlist[index].keywordGroup == kwg) and (self._kwlist[index].keyword == kw):

                if self._kwlist[index].example == 1:
                    dlg = wx.MessageDialog(TransanaGlobal.menuWindow, _('Clip "%s" has been designated as an example of Keyword "%s : %s".\nRemoving this Keyword from the Clip will also remove the Clip as a Keyword Example.\n\nDo you want to remove Clip "%s" as an example of Keyword "%s : %s"?') % (self.id, kwg, kw, self.id, kwg, kw), _("Transana Confirmation"), style=wx.YES_NO | wx.ICON_QUESTION)
                    result = dlg.ShowModal()
                    dlg.Destroy()
                    if result == wx.ID_YES:
                        # If the entry is found and the user confirms, delete it
                        del self._kwlist[index]
                        delResult = 2
                else:
                    # If the entry is found, delete it and stop looking
                    del self._kwlist[index]
                    delResult = 1
                # Once the entry has been found, stop looking for it
                break
            
        # Signal whether the delete was successful
        return delResult
            
#        if self._kwlist.count(kw) > 0:
#            self._kwlist.remove(kw)

    
# Private methods    

    def _load_row(self, r):
        self.number = r['ClipNum']
        self.id = r['ClipID']
        self.comment = r['ClipComment']
        self.collection_num = r['CollectNum']
        self.collection_id = r['CollectID']
        self.episode_num = r['EpisodeNum']
        # TranscriptNum is the Transcript Number the Clip was created FROM, not the number of the Clip Transcript!
        self.transcript_num = r['TranscriptNum']
        self.clip_transcript_num = r['ClipTranscriptNum']
        self.media_filename = r['MediaFile']
        # Remember whether the MediaFile uses the VideoRoot Folder or not.
        # Detection of the use of the Video Root Path is platform-dependent.
        if wx.Platform == "__WXMSW__":
            # On Windows, check for a colon in the position, which signals the presence or absence of a drive letter
            self.useVideoRoot = (self.media_filename[1] != ':')
        else:
            # On Mac OS-X and *nix, check for a slash in the first position for the root folder designation
            self.useVideoRoot = (self.media_filename[0] != '/')
        # If we are using the Video Root Path, add it to the Filename
        if self.useVideoRoot:
            self.media_filename = TransanaGlobal.configData.videoPath + self.media_filename
        self.clip_start = r['ClipStart']
        self.clip_stop = r['ClipStop']
        self.sort_order = r['SortOrder']
        self.text = r['RTFText']
    
    def _sync_collection(self):
        """Synchronize the Collection ID property to reflect the current state
        of the Collection Number property."""
        # For some reason the Delphi Transana didn't have anything like this
        # going on, which is especially puzzling since I can't figure out how
        # the save worked.
        # Comment by DKW -- Talk to me.  I can explain how it worked pretty easily.
        tempCollection = Collection.Collection(self.collection_num)
        self.collection_id = tempCollection.id
        
    def _get_col_num(self):
        return self._col_num
    def _set_col_num(self, num):
        self._col_num = num
    def _del_col_num(self):
        self._col_num = 0

    def _get_ep_num(self):
        return self._ep_num
    def _set_ep_num(self, num):
        self._ep_num = num
    def _del_ep_num(self):
        self._ep_num = 0

    def _get_t_num(self):
        return self._t_num
    def _set_t_num(self, num):
        self._t_num = num
    def _del_t_num(self):
        self._t_num = 0

    def _get_clip_transcript_num(self):
        return self._clip_transcript_num
    def _set_clip_transcript_num(self, num):
        self._clip_transcript_num = num
    def _del_clip_transcript_num(self):
        self._clip_transcript_num = 0

    def _get_fname(self):
        return self._fname
    def _set_fname(self, fname):
        self._fname = fname
    def _del_fname(self):
        self._fname = ""

    def _get_clip_start(self):
        return self._clip_start
    def _set_clip_start(self, cs):
        self._clip_start = cs
    def _del_clip_start(self):
        self._clip_start = -1

    def _get_clip_stop(self):
        return self._clip_stop
    def _set_clip_stop(self, cs):
        self._clip_stop = cs
    def _del_clip_stop(self):
        self._clip_stop = -1

    def _get_sort_order(self):
        return self._sort_order
    def _set_sort_order(self, so):
        self._sort_order = so
    def _del_sort_order(self):
        self._sort_order = 0

    def _get_kwlist(self):
        return self._kwlist
    def _set_kwlist(self, kwlist):
        self._kwlist = kwlist
    def _del_kwlist(self):
        self._kwlist = []

    # Clips only know originating Episode Number, which can be used to find the Series ID and Episode ID.
    # For the sake of efficiency, whichever is called first loads both values.
    def _get_series_id(self):
        # TODO:  Confirm graceful handling if originating Series/Episode has been deleted
        if self._series_id == "":
            tempEpisode = Episode.Episode(self.episode_num)
            self._series_id = tempEpisode.series_id
            self._episode_id = tempEpisode.id
            return self._series_id
        else:
            return self._series_id
        
    # Clips only know originating Episode Number, which can be used to find the Series ID and Episode ID.
    # For the sake of efficiency, whichever is called first loads both values.
    def _get_episode_id(self):
        # TODO:  Confirm graceful handling if originating Series/Episode has been deleted
        if self._episode_id == "":
            tempEpisode = Episode.Episode(self.episode_num)
            self._series_id = tempEpisode.series_id
            self._episode_id = tempEpisode.id
            return self._episode_id
        else:
            return self._episode_id

# Public properties
    collection_num = property(_get_col_num, _set_col_num, _del_col_num,
                        """Collection number to which the clip belongs.""")
    episode_num = property(_get_ep_num, _set_ep_num, _del_ep_num,
                        """Number of episode from which this Clip was taken.""")
    # TranscriptNum is the Transcript Number the Clip was created FROM, not the number of the Clip Transcript!
    transcript_num = property(_get_t_num, _set_t_num, _del_t_num,
                        """Number of the transcript from which this Clip was taken.""")
    clip_transcript_num = property(_get_clip_transcript_num, _set_clip_transcript_num, _del_clip_transcript_num,
                        """Number of the Clip's transcript record in the Transcript Table.""")
    media_filename = property(_get_fname, _set_fname, _del_fname,
                        """The name (including path) of the media file.""")
    clip_start = property(_get_clip_start, _set_clip_start, _del_clip_start,
                        """Starting position of the Clip in the media file.""")
    clip_stop = property(_get_clip_stop, _set_clip_stop, _del_clip_stop,
                        """Ending position of the Clip in the media file.""")
    sort_order = property(_get_sort_order, _set_sort_order, _del_sort_order,
                        """Sort Order position within the parent Collection.""")
    keyword_list = property(_get_kwlist, _set_kwlist, _del_kwlist,
                        """The list of keywords that have been applied to
                        the Clip.""")
    series_id = property(_get_series_id, None, None,
                        "ID for the Series from which this Clip was created, if the (bridge) Episode still exists")
    episode_id = property(_get_episode_id, None, None,
                        "ID for the Episode from which this Clip was created, if it still exists")
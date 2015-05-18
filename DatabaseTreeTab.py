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

"""This module implements the DatabaseTreeTab class for the Data Display Objects."""

__author__ = 'Nathaniel Case, David Woods <dwoods@wcer.wisc.edu>'

import wx
import TransanaConstants
import TransanaGlobal
import Series
import SeriesPropertiesForm
import Episode
import EpisodePropertiesForm
import Transcript
import TranscriptPropertiesForm
import Collection
import CollectionPropertiesForm
import Clip
import ClipPropertiesForm
import Note
import NotePropertiesForm
import Keyword                      
import KeywordPropertiesForm
import ProcessSearch
from TransanaExceptions import *
import KWManager
import exceptions
import DBInterface
import Dialogs
import NoteEditor
import os
import sys
import string
import CollectionSummaryReport
import KeywordMapClass
import KeywordUsageReport
import KeywordSummaryReport
import PlayAllClips
import DragAndDropObjects           # Implements Drag and Drop logic and objects
import cPickle                      # Used in Drag and Drop

class DatabaseTreeTab(wx.Panel):
    """This class defines the object for the "Database" tab of the Data
    window."""
    def __init__(self, parent):
        """Initialize a DatabaseTreeTab object."""
        self.parent = parent
        psize = parent.GetSizeTuple()
        width = psize[0] - 13 
        height = psize[1] - 45

        self.ControlObject = None            # The ControlObject handles all inter-object communication, initialized to None

        # Use WANTS_CHARS style so the panel doesn't eat the Enter key.
        wx.Panel.__init__(self, parent, -1, style=wx.WANTS_CHARS,
                                size=(width, height), name='DatabaseTreeTabPanel')

        #EVT_SIZE(self, self.OnSize)

        tID = wx.NewId()

        # I'll add Constraints code here in an attempt to get the tab to resize automatically with the notebook
        lay = wx.LayoutConstraints()
        lay.left.SameAs(self, wx.Left, 1)
        lay.top.SameAs(self, wx.Top, 1)
        lay.right.SameAs(self, wx.Right, 1)
        lay.bottom.SameAs(self, wx.Bottom, 1)
        self.tree = _DBTreeCtrl(self, tID, wx.DefaultPosition, self.GetSizeTuple(), wx.TR_HAS_BUTTONS | wx.TR_EDIT_LABELS)  # | wx.TR_HIDE_ROOT)
        self.tree.SetConstraints(lay)
        self.tree.SelectItem(self.tree.GetRootItem())
        
        # For Copy and Paste to work on the Mac, we need to open the Clipboard once on application startup
        # rather than opening and closing it repeatedly
        wx.TheClipboard.Open()

        self.Layout()
        self.SetAutoLayout(True)
        

    def Register(self, ControlObject=None):
        """ Register a ControlObject  for the DatabaseTreeTab to interact with. """
        self.ControlObject=ControlObject


    def add_series(self):
        """User interface for adding a new series."""
        # Create the Series Properties Dialog Box to Add a Series
        dlg = SeriesPropertiesForm.AddSeriesDialog(self, -1)
        # Set the "continue" flag to True (used to redisplay the dialog if an exception is raised)
        contin = True
        # While the "continue" flag is True ...
        while contin:
            # Display the Series Properties Dialog Box and get the data from the user
            series = dlg.get_input()
            # If the user pressed OK ...
            if series != None:
                # Use "try", as exceptions could occur
                try:
                    # Try to save the data from the form
                    self.save_series(series)
                    nodeData = (_('Series'), series.id)
                    self.tree.add_Node('SeriesNode', nodeData, series.number, 0)

                    # If we do all this, we don't need to continue any more.
                    contin = False
                # Handle "SaveError" exception
                except SaveError:
                    # Display the Error Message, allow "continue" flag to remain true
                    errordlg = Dialogs.ErrorDialog(None, sys.exc_info()[1].reason)
                    errordlg.ShowModal()
                    errordlg.Destroy()
                # Handle other exceptions
                except:
                    # Display the Exception Message, allow "continue" flag to remain true
                    errordlg = Dialogs.ErrorDialog(None, "%s" % (sys.exc_info()[:2]))
                    errordlg.ShowModal()
                    errordlg.Destroy()
                                        
            # If the user pressed Cancel ...
            else:
                # ... then we don't need to continue any more.
                contin = False
        
    def edit_series(self, series):
        """User interface for editing a series."""
        # use "try", as exceptions could occur
        try:
            # Try to get a Record Lock
            series.lock_record()
        # Handle the exception if the record is locked
        except RecordLockedError, e:
            self.handle_locked_record(e, _("Series"), series.id)
        # If the record is not locked, keep going.
        else:
            # Create the Series Properties Dialog Box to edit the Series Properties
            dlg = SeriesPropertiesForm.EditSeriesDialog(self, -1, series)
            # Set the "continue" flag to True (used to redisplay the dialog if an exception is raised)
            contin = True
            # While the "continue" flag is True ...
            while contin:
                # Display the Series Properties Dialog Box and get the data from the user
                if dlg.get_input() != None:
                    # if the user pressed "OK" ...
                    try:
                        self.save_series(series)
                        # See if the Series ID has been changed.  If it has, update the tree.
                        if series.id != self.tree.GetItemText(self.tree.GetSelection()):
                            self.tree.SetItemText(self.tree.GetSelection(), series.id)
                        # If we do all this, we don't need to continue any more.
                        contin = False
                    # Handle "SaveError" exception
                    except SaveError:
                        # Display the Error Message, allow "continue" flag to remain true
                        errordlg = Dialogs.ErrorDialog(None, sys.exc_info()[1].reason)
                        errordlg.ShowModal()
                        errordlg.Destroy()
                    # Handle other exceptions
                    except:
                        import traceback
                        traceback.print_exc(file=sys.stdout)
                        # Display the Exception Message, allow "continue" flag to remain true
                        errordlg = Dialogs.ErrorDialog(None, "Exception %s: %s" % (sys.exc_info()[0], sys.exc_info()[1]))
                        errordlg.ShowModal()
                        errordlg.Destroy()
                # If the user pressed Cancel ...
                else:
                    # ... then we don't need to continue any more.
                    contin = False
            # Unlock the record regardless of what happens
            series.unlock_record()

    def save_series(self, series):
        """Save/Update the Series object."""
        # FIXME: Graceful exception handling
        if series != None:
            series.db_save()
 
    def add_episode(self, series_name):
        """User interface for adding a new episode."""
        # Load the Series which contains the Episode
        series = Series.Series(series_name)
        # Create the Episode Properties Dialog Box to Add an Episode
        dlg = EpisodePropertiesForm.AddEpisodeDialog(self, -1, series)
        # Set the "continue" flag to True (used to redisplay the dialog if an exception is raised)
        contin = True
        # While the "continue" flag is True ...
        while contin:
            # Display the Episode Properties Dialog Box and get the data from the user
            episode = dlg.get_input()
            # If the user pressed OK ...
            if episode != None:
                # Use "try", as exceptions could occur
                try:
                    # Try to save the data from the form
                    self.save_episode(episode)
                    nodeData = (_('Series'), series.id, episode.id)
                    self.tree.add_Node('EpisodeNode', nodeData, episode.number, series.number)

                    # If we do all this, we don't need to continue any more.
                    contin = False
                    # Return the Episode Name so that the Transcript can be added to the proper Episode
                    return episode.id
                # Handle "SaveError" exception
                except SaveError:
                    # Display the Error Message, allow "continue" flag to remain true
                    errordlg = Dialogs.ErrorDialog(None, sys.exc_info()[1].reason)
                    errordlg.ShowModal()
                    errordlg.Destroy()
                # Handle other exceptions
                except:
                    # Display the Exception Message, allow "continue" flag to remain true
                    errordlg = Dialogs.ErrorDialog(None, "%s" % sys.exc_info()[:2])
                    errordlg.ShowModal()
                    errordlg.Destroy()
            # If the user pressed Cancel ...
            else:
                # ... then we don't need to continue any more.
                contin = False
                # If no Episode is created, indicate this so that no Transcript will be created.
                return None
        
    def edit_episode(self, episode):
        """User interface for editing an episode."""
        # use "try", as exceptions could occur
        try:
            # Try to get a Record Lock
            episode.lock_record()
        # Handle the exception if the record is locked
        except RecordLockedError, e:
            self.handle_locked_record(e, _("Episode"), episode.id)
        # If the record is not locked, keep going.
        else:
            # Create the Episode Properties Dialog Box to edit the Episode Properties
            dlg = EpisodePropertiesForm.EditEpisodeDialog(self, -1, episode)
            # Set the "continue" flag to True (used to redisplay the dialog if an exception is raised)
            contin = True
            # While the "continue" flag is True ...
            while contin:
                # Display the Episode Properties Dialog Box and get the data from the user
                if dlg.get_input() != None:
                    # if the user pressed "OK" ...
                    try:
                        # Try to save the Episode
                        self.save_episode(episode)
                        # See if the Episode ID has been changed.  If it has, update the tree.
                        if episode.id != self.tree.GetItemText(self.tree.GetSelection()):
                            self.tree.SetItemText(self.tree.GetSelection(), episode.id)
                        # If we do all this, we don't need to continue any more.
                        contin = False
                    # Handle "SaveError" exception
                    except SaveError:
                        # Display the Error Message, allow "continue" flag to remain true
                        errordlg = Dialogs.ErrorDialog(None, sys.exc_info()[1].reason)
                        errordlg.ShowModal()
                        errordlg.Destroy()
                    # Handle other exceptions
                    except:
                        import traceback
                        traceback.print_exc(file=sys.stdout)
                        # Display the Exception Message, allow "continue" flag to remain true
                        errordlg = Dialogs.ErrorDialog(None, "Exception %s: %s" % (sys.exc_info()[0], sys.exc_info()[1]))
                        errordlg.ShowModal()
                        errordlg.Destroy()
                # If the user pressed Cancel ...
                else:
                    # ... then we don't need to continue any more.
                    contin = False
            # Unlock the record regardless of what happens
            episode.unlock_record()

    def save_episode(self, episode):
        """Save/Update the Episode object."""
        # FIXME: Graceful exception handling
        if episode != None:
            episode.db_save()
       
    def add_transcript(self, series_name, episode_name):
        """User interface for adding a new transcript."""
        # Load the Episode Object that parents the Transcript
        episode = Episode.Episode(series=series_name, episode=episode_name)
        # Create the Transcript Properties Dialog Box to Add a Trancript
        dlg = TranscriptPropertiesForm.AddTranscriptDialog(self, -1, episode)
        # Set the "continue" flag to True (used to redisplay the dialog if an exception is raised)
        contin = True
        # While the "continue" flag is True ...
        while contin:
            # Display the Transcript Properties Dialog Box and get the data from the user
            transcript = dlg.get_input()
            # If the user pressed OK ...
            if transcript != None:
                # Use "try", as exceptions could occur
                try:
                    # Try to save the data from the form
                    self.save_transcript(transcript)
                    nodeData = (_('Series'), series_name, episode_name, transcript.id)
                    self.tree.add_Node('TranscriptNode', nodeData, transcript.number, episode.number)
                    # If we do all this, we don't need to continue any more.
                    contin = False
                    # return the Transcript ID so that it can be loaded
                    return transcript.id
                # Handle "SaveError" exception
                except SaveError:
                    # Display the Error Message, allow "continue" flag to remain true
                    errordlg = Dialogs.ErrorDialog(None, sys.exc_info()[1].reason)
                    errordlg.ShowModal()
                    errordlg.Destroy()
                # Handle other exceptions
                except:
                    # Display the Exception Message, allow "continue" flag to remain true
                    errordlg = Dialogs.ErrorDialog(None, "%s" % sys.exc_info()[:2])
                    errordlg.ShowModal()
                    errordlg.Destroy()
            # If the user pressed Cancel ...
            else:
                # ... then we don't need to continue any more.
                contin = False
                # Returning None signals that the user cancelled, so no Transcript can be loaded.
                return None

    def edit_transcript(self, transcript):
        """User interface for editing a transcript."""
        # use "try", as exceptions could occur
        try:
            # If the user tries to edit the currently-loaded Transcript ...
            if (transcript.number == self.ControlObject.TranscriptNum):
                # ... first clear all the windows ...
                self.ControlObject.ClearAllWindows()
                # ... then reload the transcript in case it got changed (saved) during the ClearAllWindows call.
                transcript.db_load_by_num(transcript.number)
            # Try to get a Record Lock.
            transcript.lock_record()
            # If the record is not locked, keep going.
            # Create the Transcript Properties Dialog Box to edit the Transcript Properties
            dlg = TranscriptPropertiesForm.EditTranscriptDialog(self, -1, transcript)
            # Set the "continue" flag to True (used to redisplay the dialog if an exception is raised)
            contin = True
            # While the "continue" flag is True ...
            while contin:
                # Display the Transcript Properties Dialog Box and get the data from the user
                if dlg.get_input() != None:
                    # if the user pressed "OK" ...
                    try:
                        self.save_transcript(transcript)
                        # See if this affects the currently loaded
                        # Transcript, in which case we have to re-load the
                        # transcript if a new one was imported.
                        if transcript.number == self.ControlObject.TranscriptNum:
                            self.ControlObject.LoadTranscript(transcript.series_id, transcript.episode_id, transcript.number)

                        # See if the Transcript ID has been changed.  If it has, update the tree.
                        if transcript.id != self.tree.GetItemText(self.tree.GetSelection()):
                            self.tree.SetItemText(self.tree.GetSelection(), transcript.id)
                        # If we do all this, we don't need to continue any more.
                        contin = False
                    # Handle "SaveError" exception
                    except SaveError:
                        # Display the Error Message, allow "continue" flag to remain true
                        errordlg = Dialogs.ErrorDialog(None, sys.exc_info()[1].reason)
                        errordlg.ShowModal()
                        errordlg.Destroy()
                    # Handle other exceptions
                    except:
                        import traceback
                        traceback.print_exc(file=sys.stdout)
                        # Display the Exception Message, allow "continue" flag to remain true
                        errordlg = Dialogs.ErrorDialog(None, "Exception %s: %s" % (sys.exc_info()[0], sys.exc_info()[1]))
                        errordlg.ShowModal()
                        errordlg.Destroy()
                # If the user pressed Cancel ...
                else:
                    # ... then we don't need to continue any more.
                    contin = False
            # Unlock the record regardless of what happens
            transcript.unlock_record()
        # Handle the exception if the record is locked
        except RecordLockedError, e:
            self.handle_locked_record(e, _("Transcript"), transcript.id)

    def save_transcript(self, transcript):
        """Save/Update the Transcript object."""
        # FIXME: Graceful exception handling
        if transcript != None:
            transcript.db_save()
       
    def add_collection(self, ParentNum):
        """User interface for adding a new collection."""
        # Create the Collection Properties Dialog Box to Add a Collection
        dlg = CollectionPropertiesForm.AddCollectionDialog(self, -1, ParentNum)
        # Set the "continue" flag to True (used to redisplay the dialog if an exception is raised)
        contin = True
        # While the "continue" flag is True ...
        while contin:
            # Display the Collection Properties Dialog Box and get the data from the user
            coll = dlg.get_input()
            # If the user pressed OK ...
            if coll != None:
                # Use "try", as exceptions could occur
                try:
                    # Try to save the data from the form
                    self.save_collection(coll)
                    nodeData = (_('Collections'),) + coll.GetNodeData()
                    # Add the new Collection to the data tree
                    self.tree.add_Node('CollectionNode', nodeData, coll.number, coll.parent)
                    # If we do all this, we don't need to continue any more.
                    contin = False
                # Handle "SaveError" exception
                except SaveError:
                    # Display the Error Message, allow "continue" flag to remain true
                    errordlg = Dialogs.ErrorDialog(None, sys.exc_info()[1].reason)
                    errordlg.ShowModal()
                    errordlg.Destroy()
                # Handle other exceptions
                except:
                    # Display the Exception Message, allow "continue" flag to remain true
                    errordlg = Dialogs.ErrorDialog(None, "%s" % sys.exc_info()[:2])
                    errordlg.ShowModal()
                    errordlg.Destroy()
            # If the user pressed Cancel ...
            else:
                # ... then we don't need to continue any more.
                contin = False

       
    def edit_collection(self, coll):
        """User interface for editing a collection."""
        # Assume failure unless proven otherwise
        success = False
        # use "try", as exceptions could occur
        try:
            # Try to get a Record Lock
            coll.lock_record()
        # Handle the exception if the record is locked
        except RecordLockedError, e:
            self.handle_locked_record(e, _("Collection"), coll.id)
        # If the record is not locked, keep going.
        else:
            # Create the Collection Properties Dialog Box to edit the Collection Properties
            dlg = CollectionPropertiesForm.EditCollectionDialog(self, -1, coll)
            # Set the "continue" flag to True (used to redisplay the dialog if an exception is raised)
            contin = True
            # While the "continue" flag is True ...
            while contin:
                # Display the Collection Properties Dialog Box and get the data from the user
                if dlg.get_input() != None:
                    # if the user pressed "OK" ...
                    try:
                        # try to save the Collection
                        self.save_collection(coll)
                        # See if the Collection ID has been changed.  If it has, update the tree.
                        if coll.id != self.tree.GetItemText(self.tree.GetSelection()):
                            self.tree.SetItemText(self.tree.GetSelection(), coll.id)
                        # If we get here, the save worked!
                        success = True
                        # If we do all this, we don't need to continue any more.
                        contin = False
                    # Handle "SaveError" exception
                    except SaveError:
                        # Display the Error Message, allow "continue" flag to remain true
                        errordlg = Dialogs.ErrorDialog(None, sys.exc_info()[1].reason)
                        errordlg.ShowModal()
                        errordlg.Destroy()
                    # Handle other exceptions
                    except:
                        import traceback
                        traceback.print_exc(file=sys.stdout)
                        # Display the Exception Message, allow "continue" flag to remain true
                        errordlg = Dialogs.ErrorDialog(None, "Exception %s: %s" % (sys.exc_info()[0], sys.exc_info()[1]))
                        errordlg.ShowModal()
                        errordlg.Destroy()
                # If the user pressed Cancel ...
                else:
                    # ... then we don't need to continue any more.
                    contin = False
            # Unlock the record regardless of what happens
            coll.unlock_record()
        # Return the "success" indicator to the calling routine
        return success

    def save_collection(self, collection):
        """Save/Update the Collection object."""
        # FIXME: Graceful exception handling
        if collection != None:
            collection.db_save()
 
    def add_clip(self, collection_id):
        """User interface for adding a Clip to a Collection."""
        # Identify the selected Tree Node and its accompanying data
        sel = self.tree.GetSelection()
        selData = self.tree.GetPyData(sel)

        # specify the data formats to accept.
        #   Our data could be a ClipDragDropData object if the source is the Transcript (clip creation)
        dfClip = wx.CustomDataFormat('ClipDragDropData')

        # Specify the data object to accept data for these formats
        #   A ClipDragDropData object will populate the cdoClip object
        cdoClip = wx.CustomDataObject(dfClip)

        # Create a composite Data Object from the object types defined above
        cdo = wx.DataObjectComposite()
        cdo.Add(cdoClip)

        # Try to get data from the Clipboard
        success = wx.TheClipboard.GetData(cdo)

        # If the data in the clipboard is in an appropriate format ...
        if success:
            # ... unPickle the data so it's in a usable form
            # Lets try to get a ClipDragDropData object
            try:
                data2 = cPickle.loads(cdoClip.GetData())
            except:
                # Windows doesn't fail this way, because success is never true above on Windows as it is on Mac
                data2 = None
                success = False
                # If this fails, that's okay
                pass

            if type(data2) == type(DragAndDropObjects.ClipDragDropData()):
                DragAndDropObjects.CreateClip(data2, selData, self.tree, sel)
            else:
                # Mac fails this way
                success = False

        # If there's not a Clip Creation object in the Clipboard, display an error message
        if not success:
            if "__WXMAC__" in wx.PlatformInfo:
                prompt = _('To add a Clip, select the desired potion of a transcript, press the "Select Clip Text" button in the\nTranscript Toolbar, then right-click the target Collection and choose "Add Clip".')
            else:
                prompt = _("To add a Clip, select the desired portion of a transcript and drag the selection onto a Collection.")
            dlg = Dialogs.InfoDialog(self, prompt)
            dlg.ShowModal()
            dlg.Destroy()
 
    def edit_clip(self, clip):
        """User interface for editing a clip."""
        # If the user wants to edit the currently-loaded Clip ...
        if ((type(self.ControlObject.currentObj) == type(Clip.Clip())) and \
            (self.ControlObject.currentObj.number == clip.number)):
            # ... we should clear the clip from the interface before editing it.
            self.ControlObject.ClearAllWindows()
            # ... then reload the clip in case it got changed (saved) during the ClearAllWindows call.
            clip.db_load_by_num(clip.number)
        # use "try", as exceptions could occur
        try:
            # Try to get a Record Lock
            clip.lock_record()
        # Handle the exception if the record is locked
        except RecordLockedError, e:
            self.handle_locked_record(e, _("Clip"), clip.id)
        # If the record is not locked, keep going.
        else:
            # Remember the clip's original name
            originalClipID = clip.id
            # Create the Clip Properties Dialog Box to edit the Clip Properties
            dlg = ClipPropertiesForm.EditClipDialog(self, -1, clip)
            # Set the "continue" flag to True (used to redisplay the dialog if an exception is raised)
            contin = True
            # While the "continue" flag is True ...
            while contin:
                # Display the Clip Properties Dialog Box and get the data from the user
                if dlg.get_input() != None:
                    # if the user pressed "OK" ...
                    try:
                        # Try to save the Clip Data
                        self.save_clip(clip)
                        # If any keywords that served as Keyword Examples that got removed from the Clip,
                        # we need to remove them from the Database Tree.  
                        for (keywordGroup, keyword, clipNum) in dlg.keywordExamplesToDelete:
                            # Load the specified Clip record
                            tempClip = Clip.Clip(clipNum)
                            # Prepare the Node List for removing the Keyword Example Node, using the clip's original name
                            nodeList = (_('Keywords'), keywordGroup, keyword, originalClipID)
                            # Call the DB Tree's delete_Node method.  Include the Clip Record Number so the correct Clip entry will be removed.
                            self.tree.delete_Node(nodeList, 'KeywordExampleNode', tempClip.number)
                        # See if the Clip ID has been changed.  If it has, update the tree.
                        if clip.id != self.tree.GetItemText(self.tree.GetSelection()):
                            clipNode = self.tree.GetSelection()
                            for (kwg, kw, clipNumber, clipID) in DBInterface.list_all_keyword_examples_for_a_clip(clip.number):
                                nodeList = (_('Keywords'), kwg, kw, self.tree.GetItemText(clipNode))
                                exampleNode = self.tree.select_Node(nodeList, 'KeywordExampleNode')
                                self.tree.SetItemText(exampleNode, clip.id)
                            self.tree.SetItemText(clipNode, clip.id)
                        # If we do all this, we don't need to continue any more.
                        contin = False
                    # Handle "SaveError" exception
                    except SaveError:
                        # Display the Error Message, allow "continue" flag to remain true
                        errordlg = Dialogs.ErrorDialog(None, sys.exc_info()[1].reason)
                        errordlg.ShowModal()
                        errordlg.Destroy()
                    # Handle other exceptions
                    except:
                        import traceback
                        traceback.print_exc(file=sys.stdout)
                        # Display the Exception Message, allow "continue" flag to remain true
                        errordlg = Dialogs.ErrorDialog(None, "Exception %s: %s" % (sys.exc_info()[0], sys.exc_info()[1]))
                        errordlg.ShowModal()
                        errordlg.Destroy()
                # If the user pressed Cancel ...
                else:
                    # ... then we don't need to continue any more.
                    contin = False
            # Unlock the record regardless of what happens
            clip.unlock_record()

    def save_clip(self, clip):
        """Save/Update the Clip object."""
        # FIXME: Graceful exception handling
        if clip != None:
            clip.db_save()

    def add_note(self, seriesNum=0, episodeNum=0, transcriptNum=0, collectionNum=0, clipNum=0):
        """User interface method for adding a Note to an object."""
        # Create the Note Properties Dialog Box to Add a Note
        dlg = NotePropertiesForm.AddNoteDialog(self, -1, seriesNum, episodeNum, transcriptNum, collectionNum, clipNum)
        # Set the "continue" flag to True (used to redisplay the dialog if an exception is raised)
        contin = True
        # While the "continue" flag is True ...
        while contin:
            # Display the Note Properties Dialog Box and get the data from the user
            note = dlg.get_input()
            # If the user pressed OK ...
            if note != None:
                # Create the Note Editing Form
                noteedit = NoteEditor.NoteEditor(self, note.text)
                # Display the Node Editing Form and get the user's input
                note.text = noteedit.get_text()
                # Use "try", as exceptions could occur
                try:
                    # Try to save the data from the forms
                    self.save_note(note)

                    if seriesNum != 0:
                        nodeType = 'SeriesNoteNode'
                        series = Series.Series(seriesNum)
                        nodeData = (_('Series'), series.id, note.id)
                        parentNum = series.number
                    elif episodeNum != 0:
                        nodeType = 'EpisodeNoteNode'
                        episode = Episode.Episode(num = episodeNum)
                        nodeData = (_('Series'), episode.series_id, episode.id, note.id)
                        parentNum = episode.number
                    elif transcriptNum != 0:
                        nodeType = 'TranscriptNoteNode'
                        transcript = Transcript.Transcript(transcriptNum)
                        episode = Episode.Episode(num = transcript.episode_num)
                        nodeData = (_('Series'), episode.series_id, episode.id, transcript.id, note.id)
                        parentNum = transcript.number
                    elif collectionNum != 0:
                        nodeType = 'CollectionNoteNode'
                        collection = Collection.Collection(collectionNum)
                        nodeData = (_('Collections'),) + collection.GetNodeData() + (note.id,)
                        parentNum = collection.number  # This is the NOTE's parent, not the Collection's parent!!
                    elif clipNum != 0:
                        nodeType = 'ClipNoteNode'
                        clip = Clip.Clip(clipNum)
                        collection = Collection.Collection(clip.collection_num)
                        nodeData = (_('Collections'),) + collection.GetNodeData() + (clip.id, note.id)
                        parentNum = clip.number
                    else:
                        errordlg = Dialogs.ErrorDialog(None, 'Not Yet Implemented in DatabaseTreeTab.add_note()')
                        errordlg.ShowModal()
                        errordlg.Destroy()
                        
                    self.tree.add_Node(nodeType, nodeData, note.number, parentNum)
                    
                    # If we do all this, we don't need to continue any more.
                    contin = False
                # Handle "SaveError" exception
                except SaveError:
                    # Display the Error Message, allow "continue" flag to remain true
                    errordlg = Dialogs.ErrorDialog(None, sys.exc_info()[1].reason)
                    errordlg.ShowModal()
                    errordlg.Destroy()
                # Handle other exceptions
                except:
                    # Display the Exception Message, allow "continue" flag to remain true
                    errordlg = Dialogs.ErrorDialog(None, "%s" % sys.exc_info()[:2])
                    errordlg.ShowModal()
                    errordlg.Destroy()
            # If the user pressed Cancel ...
            else:
                # ... then we don't need to continue any more.
                contin = False

    def edit_note(self, note):
        """User interface for editing a note."""
        # use "try", as exceptions could occur
        try:
            # Try to get a Record Lock
            note.lock_record()
        # Handle the exception if the record is locked
        except RecordLockedError, e:
            self.handle_locked_record(e, _("Note"), note.id)
        # If the record is not locked, keep going.
        else:
            # Create the Note Properties Dialog Box to edit the Note Properties
            dlg = NotePropertiesForm.EditNoteDialog(self, -1, note)
            # Set the "continue" flag to True (used to redisplay the dialog if an exception is raised)
            contin = True
            # While the "continue" flag is True ...
            while contin:
                # Display the Note Properties Dialog Box and get the data from the user
                if dlg.get_input() != None:
                    # if the user pressed "OK" ...
                    try:
                        # Try to save the Note Data
                        self.save_note(note)
                        # See if the Note ID has been changed.  If it has, update the tree.
                        if note.id != self.tree.GetItemText(self.tree.GetSelection()):
                            self.tree.SetItemText(self.tree.GetSelection(), note.id)
                        # If we do all this, we don't need to continue any more.
                        contin = False
                    # Handle "SaveError" exception
                    except SaveError:
                        # Display the Error Message, allow "continue" flag to remain true
                        errordlg = Dialogs.ErrorDialog(None, sys.exc_info()[1].reason)
                        errordlg.ShowModal()
                        errordlg.Destroy()
                    # Handle other exceptions
                    except:
                        import traceback
                        traceback.print_exc(file=sys.stdout)
                        # Display the Exception Message, allow "continue" flag to remain true
                        errordlg = Dialogs.ErrorDialog(None, "Exception %s: %s" % (sys.exc_info()[0], sys.exc_info()[1]))
                        errordlg.ShowModal()
                        errordlg.Destroy()
                # If the user pressed Cancel ...
                else:
                    # ... then we don't need to continue any more.
                    contin = False
            # Unlock the record regardless of what happens
            note.unlock_record()

    def save_note(self, note):
        """Save/Update the Note object."""
        # FIXME: Graceful exception handling
        if note != None:
            note.db_save()

    def add_keyword(self, keywordGroup):
        """User interface for adding a new keyword."""
        # Create the Keyword Properties Dialog Box to Add a Keyword
        dlg = KeywordPropertiesForm.AddKeywordDialog(self, -1, keywordGroup)
        # Set the "continue" flag to True (used to redisplay the dialog if an exception is raised)
        contin = True
        # While the "continue" flag is True ...
        while contin:
            # Display the Keyword Properties Dialog Box and get the data from the user
            kw = dlg.get_input()
            # If the user pressed OK ...
            if kw != None:
                # Use "try", as exceptions could occur
                try:
                    # Try to save the data from the form
                    self.save_keyword(kw)
                    # Add the new Keyword to the tree
                    self.tree.add_Node('KeywordNode', (_('Keywords'), kw.keywordGroup, kw.keyword), 0, kw.keywordGroup)
                    # If we do all this, we don't need to continue any more.
                    contin = False
                # Handle "SaveError" exception
                except SaveError:
                    # Display the Error Message, allow "continue" flag to remain true
                    errordlg = Dialogs.ErrorDialog(None, sys.exc_info()[1].reason)
                    errordlg.ShowModal()
                    errordlg.Destroy()
                # Handle other exceptions
                except:
                    # Display the Exception Message, allow "continue" flag to remain true
                    errordlg= Dialogs.ErrorDialog(None, "%s" % sys.exc_info()[:2])
                    errordlg.ShowModal()
                    errordlg.Destroy()
            # If the user pressed Cancel ...
            else:
                # ... then we don't need to continue any more.
                contin = False
        
    def edit_keyword(self, kw):
        """User interface for editing a keyword."""
        # use "try", as exceptions could occur
        try:
            # Try to get a Record Lock
            kw.lock_record()
        # Handle the exception if the record is locked
        except RecordLockedError, e:
            self.handle_locked_record(e, _("Keyword"), kw.keywordGroup + ':' + kw.keyword)
        # If the record is not locked, keep going.
        else:
            # Create the Keyword Properties Dialog Box to edit the Keyword Properties
            dlg = KeywordPropertiesForm.EditKeywordDialog(self, -1, kw)
            # Set the "continue" flag to True (used to redisplay the dialog if an exception is raised)
            contin = True
            # While the "continue" flag is True ...
            while contin:
                # Display the Keyword Properties Dialog Box and get the data from the user
                if dlg.get_input() != None:
                    # if the user pressed "OK" ...
                    try:
                        # Try to save the Keyword Data
                        self.save_keyword(kw)

                        # See if the Keyword Group or Keyword has been changed.  If it has, update the tree.
                        if kw.keywordGroup != self.tree.GetItemText(self.tree.GetItemParent(self.tree.GetSelection())):
                            # If the Keyword Group has changed, delete the Keyword Node, insert the new
                            # keyword group node if necessary, and insert the keyword in the right keyword
                            # group node
                            # Remove the old Keyword from the Tree
                            self.tree.delete_Node((_('Keywords'), self.tree.GetItemText(self.tree.GetItemParent(self.tree.GetSelection())), self.tree.GetItemText(self.tree.GetSelection())), 'KeywordNode')
                            # Add the new Keyword to the tree
                            self.tree.add_Node('KeywordNode', (_('Keywords'), kw.keywordGroup, kw.keyword), 0, kw.keywordGroup)
                        elif kw.keyword != self.tree.GetItemText(self.tree.GetSelection()):
                            # If only the Keyword has changed, simply rename the node
                            self.tree.SetItemText(self.tree.GetSelection(), kw.keyword)
                        # If we do all this, we don't need to continue any more.
                        contin = False
                    # Handle "SaveError" exception
                    except SaveError:
                        # Display the Error Message, allow "continue" flag to remain true
                        errordlg = Dialogs.ErrorDialog(None, sys.exc_info()[1].reason)
                        errordlg.ShowModal()
                        errordlg.Destroy()
                    # Handle other exceptions
                    except:
                        import traceback
                        traceback.print_exc(file=sys.stdout)
                        # Display the Exception Message, allow "continue" flag to remain true
                        errordlg = Dialogs.ErrorDialog(None, "Exception %s: %s" % (sys.exc_info()[0], sys.exc_info()[1]))
                        errordlg.ShowModal()
                        errordlg.Destroy()
                # If the user pressed Cancel ...
                else:
                    # ... then we don't need to continue any more.
                    contin = False
            # Unlock the record regardless of what happens
            kw.unlock_record()


    def save_keyword(self, kw):
        """Save/Update the Keyword object."""
        # FIXME: Graceful exception handling
        if kw != None:
            kw.db_save()
 

    def handle_locked_record(self, e, rtype, id):
        """Handle the RecordLockedError exception."""
        msg = \
        _('You cannot proceed because you cannot obtain a lock on %s "%s"' + \
          '.\nThe record is currently locked by %s.\nPlease try again later.') \
                % (rtype, id, e.user)
        wx.MessageDialog(self, msg).ShowModal()



class MenuIDError(exceptions.Exception):
    def __init__(self, id=-1, menu=""):
        if id > -1:
            self.msg = \
                _("Unable to handle selection menu ID %d for '%s' menu") \
                %  (id, menu)
        else:
            self.msg = _("Unable to handle menu ID selection")
        self.args = self.msg


class _NodeData:
    """ This class defines the information that is known about each node in the Database Tree. """

    # NOTE:  _NodeType and DataTreeDragDropData have very similar structures so that they can be
    #        used interchangably.  If you alter one, please also alter the other.
   
    def __init__(self, nodetype='Unknown', recNum=0, parent=0):
        self.nodetype = nodetype    # nodetype indicates what sort of node we have.  Options include:
                                    # Root, SeriesRootNode, SeriesNode, EpisodeNode, TranscriptNode,
                                    # CollectionsRootNode, CollectionNode, ClipNode,
                                    # KeywordsRootNode, KeywordGroupNode, KeywordNode,
                                    # NotesGroupNode, NoteNode,
                                    # SearchRootNode, SearchResultsNode, SearchSeriesNode, SearchEpisodeNode,
                                    # SearchTranscriptNode, SearchCollectionNode, SearchClipNode
        self.recNum = recNum        # recNum indicates the Database Record Number of the node
        self.parent = parent        # parent indicates the parent Record Number for nested Collections

    def __repr__(self):
        """ Provides a string representation of the data in the _NodeData object """
        str = 'nodetype = %s, recNum = %s, parent = %s' % (self.nodetype, self.recNum, self.parent)
        return str


        

class _DBTreeCtrl(wx.TreeCtrl):
    """Private class that implements the details of the tree widget."""
    def __init__(self, parent, id, pos, size, style):
        wx.TreeCtrl.__init__(self, parent, id, pos, size, style)
        
        self.cmd_id = TransanaConstants.DATA_MENU_CMD_OFSET
        self.parent = parent
        
        # Track the number of Searches that have been requested
        self.searchCount = 1

        # Create image list of 16x16 object icons
        self.icon_list = ["Clip16", "Collection16", "Episode16", "Keyword16",
                        "KeywordGroup16", "KeywordRoot16", "Note16",
                        "NoteNode16", "Series16", "SeriesRoot16", "SearchRoot16", "Search16",
                        "Transcript16", "db", ]
        self.image_list = wx.ImageList(16, 16, 0, len(self.icon_list))
        for icon_file in self.icon_list:
            fname = "images/" + icon_file + ".xpm"
            bitmap = wx.Bitmap(fname, wx.BITMAP_TYPE_XPM)
            self.image_list.Add(bitmap)
    
        self.SetImageList(self.image_list)

        # Remove Drag-and-Drop reference on the mac due to the Quicktime Drag-Drop bug
        if not '__WXMAC__' in wx.PlatformInfo:
            # Define the Drop Target for the tree.  The custom drop target object
            # accepts the tree as a parameter so it can query it about where the
            # drop is supposed to be occurring to see if it will allow the drop.
            dt = DragAndDropObjects.DataTreeDropTarget(self)
            self.SetDropTarget(dt)
        
        self.refresh_tree()

        self.create_menus()

        # Initialize the cutCopyInfo Dictionary to empty values.
        # This information is used to facilitate Cut, Copy, and Paste functionality.
        self.cutCopyInfo = {'action': 'None', 'sourceItem': None, 'destItem': None}
        
        # Define the Begin Drag Event for the Database Tree Tab.  This enables Drag and Drop.
        wx.EVT_TREE_BEGIN_DRAG(self, id, self.OnCutCopyBeginDrag)

        # wx.EVT_MOTION(self, self.OnMotion)

        # Right Down initiates popup menu
        wx.EVT_RIGHT_DOWN(self, self.OnRightDown)

        # This processes double-clicks in the Tree Control
        wx.EVT_TREE_ITEM_ACTIVATED(self, id, self.OnItemActivated)

        # Prevent the ability to Edit Node Labels unless it is in a Search Result
        # or is explicitly processed in OnEndLabelEdit()
        wx.EVT_TREE_BEGIN_LABEL_EDIT(self, id, self.OnBeginLabelEdit)

        # Process Database Tree Label Edits
        wx.EVT_TREE_END_LABEL_EDIT(self, id, self.OnEndLabelEdit)


    def set_image(self, item, icon_name):
        """Set the item's icon image for all states."""
        index = self.icon_list.index(icon_name)
        self.SetItemImage(item, index, wx.TreeItemIcon_Normal)
        self.SetItemImage(item, index, wx.TreeItemIcon_Selected)
        self.SetItemImage(item, index, wx.TreeItemIcon_Expanded)
        self.SetItemImage(item, index, wx.TreeItemIcon_SelectedExpanded)
        
    # FIXME: Doesn't preserve node 'expanded' states
    def refresh_tree(self, evt=None):
        """Load information from database and re-create the tree."""
        self.DeleteAllItems()
        self.transcripts = []
        self.notes = []
        self.create_root_node()
        self.create_series_node()
        self.create_collections_node()
        self.create_kwgroups_node()
        self.create_search_node()
        self.Expand(self.root)

        
    def OnMotion(self, event):
        """ Detects Mouse Movement in the Database Tree Tab so that we can scroll as needed
            during Drag-and-Drop operations. """

        # Detect if a Drag is currently under way

        # NOTE:  Although I'm sure this code USED to work, it no longer gets called during Dragging.
        #        I don't know if this coincided with going to 2.4.2.4, or whether there is some other aspect
        #        of our Drag-and-drop code that is causing this problem.
        
        # Remove Drag-and-Drop reference on the mac due to the Quicktime Drag-Drop bug
        if not '__WXMAC__' in wx.PlatformInfo:
            if event.Dragging():
                # Get the Mouse position
                (x,y) = event.GetPosition()
                # Get the dimensions of the Database Tree Tab window
                (w, h) = self.GetClientSizeTuple()
                # If we are dragging at the top of the window, scroll down
                if y < 8:
                    self.ScrollLines(-2)
                # If we are dragging at the bottom of the window, scroll up
                elif y > h - 8:
                    self.ScrollLines(2)
            # If we're not dragging, don't do anything
            else:
                pass
        else:
            pass
        

    def OnCutCopyBeginDrag(self, event):
        """ Fired on the initiation of a Drag within the Database Tree Tab or by the selection
            of "Cut" or "Copy" from the popup menus.  """

        # The first thing we need to do is determine what tree item is being cut, copied, or dragged.
        # For drag, we just look at the mouse position to determine the item.  However, for Cut and Copy,
        # the mouse position will reflect the position of the the popup menu item selected rather than 
        # the position of the tree item selected.  However, the cutCopyInfo variable will contain that
        # information.

        # SearchCollectionNodes and SearchClipNodes need their Node Lists included in the SourceData Object
        # so that the correct tree node can be deleted during "Cut/Move" operations.  (I've tried several other
        # approaches, but they've failed.)
        # To be able to do this, we need to initialize the nodeList to empty.
        nodeList = ()

        # Detect if this event has been fired by a "Cut" or "Copy" request.  (Collections, Clips, Keywords,
        # SearchCollections, and SearchClips have
        # "Cut" options as their first menu items and "Copy" as their second menu items.)
        if event.GetId() in [self.cmd_id_start["collection"],           self.cmd_id_start["clip"],           self.cmd_id_start["kw"],
                             self.cmd_id_start["searchcollection"],     self.cmd_id_start["searchclip"],
                             self.cmd_id_start["collection"] + 1,       self.cmd_id_start["clip"] + 1,        self.cmd_id_start["kw"] + 1,
                             self.cmd_id_start["searchcollection"] + 1, self.cmd_id_start["searchclip"] + 1]:
            # If "Cut" or "Copy", get the selected item from cutCopyInfo
            sel_item = self.cutCopyInfo['sourceItem']
            
        # If this method is not triggered by a "Cut" or "Copy" request, it was fired by the initiation of a Drag.
        else:
            # Items in the tree are not automatically selected with a left click.
            # We must select the item that is initially clicked manually!!
            # We do this by looking at the screen point clicked and applying the tree's
            # HitTest method to determine the current item, then actually selecting the item

            # This line works on Windows, but not on Mac or Linux using wxPython 2.4.1.2  due to a problem with event.GetPoint().
            # pt = event.GetPoint()
            # therfore, this alternate method is used.
            # Get the Mouse Position on the Screen in a more generic way to avoid the problem above
            (windowx, windowy) = wx.GetMousePosition()
            # Translate the Mouse's Screen Position to the Mouse's Control Position
            pt = self.ScreenToClientXY(windowx, windowy)
            # use HitTest to determine the tree item as the screen point indicated.
            sel_item, flags = self.HitTest(pt)

        # Select the appropriate item in the TreeCtrl
        self.SelectItem(sel_item)

        # Determine what Item is being cut, copied, or dragged, and grab it's data
        tempNodeName = "%s" % (self.GetItemText(sel_item))
        tempNodeData = self.GetPyData(sel_item)
        
        # If we're dealing with a SearchCollection or SearchClip Node, let's build the nodeList.
        if tempNodeData.nodetype == 'SearchCollectionNode' or \
           tempNodeData.nodetype == 'SearchClipNode':
            # Start with a Node Pointer
            tempNode = sel_item
            # Start the node List with that nodePointer's Text
            nodeList = (self.GetItemText(tempNode),)
            # Climb the tree up to the Search Root Node ...
            while self.GetPyData(tempNode).nodetype != 'SearchRootNode':
                # Get the Parent Node ...
                tempNode = self.GetItemParent(tempNode)
                # And add it's text to the Node List
                nodeList = (self.GetItemText(tempNode),) + nodeList

        # Create a custom Data Object for Cut and Paste AND Drag and Drop
        ddd = DragAndDropObjects.DataTreeDragDropData(text=tempNodeName, nodetype=tempNodeData.nodetype, nodeList=nodeList, recNum=tempNodeData.recNum, parent=tempNodeData.parent)

        # Use cPickle to convert the data object into a string representation
        pddd = cPickle.dumps(ddd, 1)

        # Now create a wxCustomDataObject for dragging and dropping and
        # assign it a custom Data Format
        cdo = wx.CustomDataObject(wx.CustomDataFormat('DataTreeDragData'))
        # Put the pickled data object in the wxCustomDataObject
        cdo.SetData(pddd)

        # If we have a "Cut" or "Copy" request, we put the pickled CustomDataObject in the Clipboard.
        # If we have a "Drag", we put the pickled CustomDataObject in the DropSource Object.

        # If the event was triggered by a "Cut" or "Copy" request ...
        if event.GetId() in [self.cmd_id_start["collection"],           self.cmd_id_start["clip"],           self.cmd_id_start["kw"],
                             self.cmd_id_start["searchcollection"],     self.cmd_id_start["searchclip"],
                             self.cmd_id_start["collection"] + 1,       self.cmd_id_start["clip"] + 1,        self.cmd_id_start["kw"] + 1,
                             self.cmd_id_start["searchcollection"] + 1, self.cmd_id_start["searchclip"] + 1]:
            # ... open the clipboard ...
            # wx.TheClipboard.Open()
            # ... put the data in the clipboard ...
            wx.TheClipboard.SetData(cdo)
            # ... and close the clipboard.
            # wx.TheClipboard.Close()
            
        # If the event was triggered by a "Drag" request ...
        elif not '__WXMAC__' in wx.PlatformInfo:
            # Create a Custom DropSource Object.  The custom drop source object
            # accepts the tree as a parameter so it can query it about where the
            # drop is supposed to be occurring to see if it will allow the drop.
            tds = DragAndDropObjects.DataTreeDropSource(self)
            # Associate the Data with the Drop Source Object
            tds.SetData(cdo)
            # Initiate the Drag Operation
            dragResult = tds.DoDragDrop(True)
            # We do the actual processing in the DropTarget object, as we have access to the Dragged Data and the
            # Drop Target's information there but not here.

            # TODO:  In Transana, this is unnecessary and should be deleted.
            # Report the result of the final drop when everything else is completed by the other objects.
#            if dragResult == wx.DragCopy:
#               print "_DBTreeCtrl OnBeginDrag Result indicated successful copy"
#           elif dragResult == wx.DragMove:
#               print "_DBTreeCtrl OnBeginDrag Result indicated successful move"
#            else:
#               print "_DBTreeCtrl OnBeginDrag Result indicated failed drop"
#               print

            # Because the DropSource GiveFeedback Method can change the cursor, I find that I
            # need to reset it to "normal" here or it can get stuck as a "No_Entry" cursor if
            # a Drop is abandoned.
            self.SetCursor(wx.StockCursor(wx.CURSOR_ARROW))


    def create_root_node(self):
        # Include the Database Name as part of the Database Root
        self.root = self.AddRoot(_('Database: %s') % TransanaGlobal.configData.database)
        self.set_image(self.root, "db")
        nodedata = _NodeData(nodetype='Root')                    # Identify this as the Root node
        self.SetPyData(self.root, nodedata)                      # Associate this data with the node
      
    def add_note_nodes(self, note_ids, item, **parent_num):
        if len(note_ids) > 0:
            for n in note_ids:
                noteitem = self.AppendItem(item, n)
                self.set_image(noteitem, "Note16")
                self.notes.append(noteitem)
                n = Note.Note(n, **parent_num)
                nodedata = _NodeData(nodetype='NoteNode', recNum=n.number)  # Identify this as a Note node
                self.SetPyData(noteitem, nodedata)                          # Associate this data with the node
                del n

    def create_series_node(self):
        self.series = []
        self.episodes = []
        # The 'Series' node itself is always item 0 in the series node list
        root_item = self.AppendItem(self.root, _("Series"))
        nodedata = _NodeData(nodetype='SeriesRootNode')          # Idenfify this as the Series Root node
        self.SetPyData(root_item, nodedata)                      # Associate this data with the node
        self.set_image(root_item, "SeriesRoot16")
        self.series.append(root_item)

        for (seriesNo, seriesID) in DBInterface.list_of_series():
            # Add children of this series to the series node list
            item = self.AppendItem(self.series[0], seriesID)
            nodedata = _NodeData(nodetype='SeriesNode', recNum=seriesNo)          # Identify this as a Series node
            self.SetPyData(item, nodedata)                       # Associate this data with the node
            self.set_image(item, "Series16")
            self.series.append(item)
           
            for (episodeNo, episodeID, episodeSeriesNo) in DBInterface.list_of_episodes_for_series(seriesID):
                epitem = self.AppendItem(self.series[-1], episodeID)
                nodedata = _NodeData(nodetype='EpisodeNode', recNum=episodeNo, parent=episodeSeriesNo)     # Identify this as an Episode node
                self.SetPyData(epitem, nodedata)                 # Associate this data with the node
                self.set_image(epitem, "Episode16")
                self.episodes.append(epitem)
                for (transcriptNo, transcriptID, transcriptEpisodeNo) in DBInterface.list_transcripts(seriesID, episodeID):
                    titem = self.AppendItem(epitem, transcriptID)
                    nodedata = _NodeData(nodetype='TranscriptNode', recNum=transcriptNo, parent=transcriptEpisodeNo)  # Identify this as a Transcript node
                    self.SetPyData(titem, nodedata)                  # Associate this data with the node
                    self.set_image(titem, "Transcript16")
                    self.transcripts.append(titem)
                    # NOTE:  This call passes the Transcript NUMBER rather than strings.
                    notes = DBInterface.list_of_notes(Transcript=transcriptNo)
                    if len(notes) > 0:
                        self.add_note_nodes(notes, titem, Transcript=transcriptNo)

                notes = DBInterface.list_of_notes(Episode=episodeNo)
                if len(notes) > 0:
                    # ep = Episode.Episode(series=s, episode=e)
                    self.add_note_nodes(notes, epitem, Episode=episodeNo)
    
            notes = DBInterface.list_of_notes(Series=seriesNo)
            if len(notes) > 0:
                # series = Series.Series(s)
                self.add_note_nodes(notes, item, Series=seriesNo)

    def create_collection_node(self, collNo, collID, parentCollNo, root_item):
        """Recursively add a Collection node to a tree."""
        # A certain bit of trickery is involved here to put Collection Contents in the order of
        # Nested Collections, then Clips, then Notes.
        # If the current collection has no children, simply put the new collection on the end.
        if not(self.ItemHasChildren(root_item)):
            # Add the Collection node
            item = self.AppendItem(root_item, collID)
        else:
            # Otherwise, let's look through the children and find the proper place for the new Collection.
            # first find the first child.
            (child, cookieVal) = self.GetFirstChild(root_item)
            # to insert, we need to track the POSITION of our nodes in the tree.
            nodeCounter = 0
            # As long as we have a valid child, we have not exceeded our alphabetic position, and we still are looking at
            # Nested Collections, we keep looking through the children as we have not yet found the right place for the new node.
            while child.IsOk() and (collID > self.GetItemText(child)) and (self.GetPyData(child).nodetype == 'CollectionNode'):
                # Get the next child
                (child, cookieVal) = self.GetNextChild(root_item, cookieVal)
                # and increment our position counter
                nodeCounter += 1
            # If we did not reach the end of the list ...
            if child.IsOk():
                # ... insert the new item before the one that caused us to stop ...
                item = self.InsertItemBefore(root_item, nodeCounter, collID)
            else:
                # ... otherwise, just stick it on the end.
                item = self.AppendItem(root_item, collID)
        # Identify this as a Collection node with the proper Node Data
        nodedata = _NodeData(nodetype='CollectionNode', recNum=collNo, parent=parentCollNo)
        # Associate this data with the node
        self.SetPyData(item, nodedata)
        # Select the proper image
        self.set_image(item, "Collection16")
        # Add this item to our Collections list
        self.collections.append(item)

        # Add its Clips as children.
        # Each Clip Record consist of Clip Number in the Clips Table, Clip ID, and parent Collection Number
        for (clipNo, clipID, collNo) in DBInterface.list_of_clips_by_collection(collID, parentCollNo):
            # Display the Clip ID
            clip_item = self.AppendItem(item, clipID)
            # Store both Node Type and Record Number in the Node Data.  
            nodedata = _NodeData(nodetype='ClipNode', recNum=clipNo, parent=collNo)       # Identify this as a Clip node
            self.SetPyData(clip_item, nodedata)                           # Associate this data with the node
            self.set_image(clip_item, "Clip16")
            self.clips.append(clip_item)
            notes = DBInterface.list_of_notes(Clip=clipNo)
            if len(notes) > 0:
                # clip = Clip.Clip(c, name, root_rec)
                self.add_note_nodes(notes, clip_item, Clip=clipNo)
   
        notes = DBInterface.list_of_notes(Collection=collNo)
        if len(notes) > 0:
            self.add_note_nodes(notes, item, Collection=collNo)

        # Add its Collections as children.  This must be done LAST because the recursive call to
        # create_collection_node causes problems for our "item" variable, which does not return from
        # the recursive call in the correct state.
        for (collNo, collID, parentCollNo) in DBInterface.list_of_collections(collNo):
            self.create_collection_node(collNo, collID, parentCollNo, item)

    def create_collections_node(self):
        self.collections = []
        # The 'Collections' node itself is always item 0 in the node list
        self.collections.append(self.AppendItem(self.root, _("Collections")))

        self.clips = []
        root_item = self.collections[0]
        nodedata = _NodeData(nodetype='CollectionsRootNode')     # Identify this as the Collections Root node
        self.SetPyData(root_item, nodedata)                      # Associate this data with the node
        self.set_image(root_item, "Collection16")
        
        for (collNo, collID, parentCollNo) in DBInterface.list_of_collections(0):
            self.create_collection_node(collNo, collID, parentCollNo, root_item)
            
    def create_kwgroups_node(self):
        # The "Keywords" node itself is always item 0 in the node list
        kwg_root = self.AppendItem(self.root, _("Keywords"))
        nodedata = _NodeData(nodetype='KeywordRootNode')         # Identify this as the Keywords Root node
        self.SetPyData(kwg_root, nodedata)                       # Associate this data with the node
        self.set_image(kwg_root, "KeywordRoot16")

        self.refresh_kwgroups_node()
        
    def refresh_kwgroups_node(self):
        # remember the current selection in the tree
        sel = self.GetSelection()
        # Initialize keyword groups to an empty list
        self.kwgroups = []
        # The "Keywords" node itself is always item 0 in the node list
        kwg_root = self.select_Node((_("Keywords"),), 'KeywordRootNode')
        self.DeleteChildren(kwg_root)
        self.kwgroups.append(kwg_root)
        for s in DBInterface.list_of_keyword_groups():
            # Add children in this Keyword group to the kwgroups node list
            kwg_item = self.AppendItem(self.kwgroups[0], s)
            nodedata = _NodeData(nodetype='KeywordGroupNode')    # Identify this as a Keyword Group node
            self.SetPyData(kwg_item, nodedata)                   # Associate this data with the node
            self.set_image(kwg_item, "KeywordGroup16")
            self.kwgroups.append(kwg_item)
            for kw in DBInterface.list_of_keywords_by_group(s):
                kw_item = self.AppendItem(self.kwgroups[-1], kw)
                nodedata = _NodeData(nodetype='KeywordNode', parent=s)     # Identify this as a Keyword node
                self.SetPyData(kw_item, nodedata)                # Associate this data with the node
                self.set_image(kw_item, "Keyword16")
        self.addKeywordExamples()
        # Reset the selection in the Tree to what it was before we called this method
        self.SelectItem(sel)
        # Refresh the Tree Node so that changes are displayed appropriately (such as new children are indicated if the node was empty)
        self.Refresh()

    def addKeywordExamples(self):
        """ Get a list of all Keyword Examples and insert them into the tree """
        # NOTE:  The Delphi version of Transana checked every KWG:KW combination as it was building the
        #        tree and inserted Keyword Examples as it went.  I think that was a very inefficient strategy,
        #        as I imagine Keyword Examples are probably fairly rare.  This method of calling up all the
        #        Keyword Examples at once and inserting nodes in the tree should be more efficient and cause
        #        MANY fewer database calls on startup.

        # Get a list of all Keyword Examples from the Database
        keywordExamples = DBInterface.list_of_keyword_examples()

        # Iterate through the examples
        for rowData in keywordExamples:
            # Load the indicated clip
            exampleClip = Clip.Clip(rowData[1])
            # Determine where it should be displayed in the Node Structure.
            # (Keyword Root, Keyword Group, Keyword, Example Clip Name)
            nodeData = (_('Keywords'), rowData[2], rowData[3], exampleClip.id)
            # Add the Keyword Example Node to the Database Tree Tab, but don't expand the nodes
            self.add_Node("KeywordExampleNode", nodeData, exampleClip.number, exampleClip.collection_num, False)

    def create_search_node(self):
        self.searches = []
        # The "Search" node itself is always item 0 in the node list
        search_root = self.AppendItem(self.root, _("Search"))
        nodedata = _NodeData(nodetype='SearchRootNode')          # Identify this as the Search Root node
        self.SetPyData(search_root, nodedata)                    # Associate this data with the node
        self.set_image(search_root, "SearchRoot16")
        self.searches.append(search_root)

    def UpdateExpectedNodeType(self, expectedNodeType, nodeListPos, nodeData, nodeType):
        """ This function returns the node type of the Next Node that should be examined.
            Used in crawling the Database Tree.
            Paramters are:
              expectedNodeType  The current anticipated Node Type
              nodeListPos       The position in the current Node List of the current node
              nodeData          The current Node List
              nodeType          The Node Type of the LAST element in the Node List """

        # First, let's see if we're dealing with a NOTE, as the next node is different if we are.
        if ((nodeListPos == len(nodeData) - 1) and (nodeType in ['NoteNode', 'SeriesNoteNode', 'EpisodeNoteNode', 'TranscriptNoteNode',
                                                                 'CollectionNoteNode', 'ClipNoteNode'])):
            expectedNodeType = 'NoteNode'
        # For ClipNotes only, we need to move from Collection to Clip at the second-to-last node
        elif ((nodeListPos == len(nodeData) - 2) and (nodeType == 'ClipNoteNode')):
            expectedNodeType = 'ClipNode'
        elif expectedNodeType == 'SeriesRootNode':
            expectedNodeType = 'SeriesNode'
        elif expectedNodeType == 'SeriesNode':
            expectedNodeType = 'EpisodeNode'
        elif expectedNodeType == 'EpisodeNode':
            expectedNodeType = 'TranscriptNode'
        elif expectedNodeType == 'CollectionsRootNode':
            expectedNodeType = 'CollectionNode'
        # CollectionNode only advances to ClipNode if we're reaching the end of the nodeList AND we're supposed to move on to a clip
        elif (expectedNodeType == 'CollectionNode') and ((nodeListPos == len(nodeData) - 1) and (nodeType in ['ClipNode'])):
            expectedNodeType = 'ClipNode'
        elif expectedNodeType == 'KeywordRootNode':
            expectedNodeType = 'KeywordGroupNode'
        elif expectedNodeType == 'KeywordGroupNode':
            expectedNodeType = 'KeywordNode'
        elif expectedNodeType == 'KeywordNode':
            expectedNodeType = 'KeywordExampleNode'
        elif expectedNodeType == 'SearchRootNode':
            expectedNodeType = 'SearchResultsNode'
        elif (expectedNodeType == 'SearchResultsNode') and (nodeType in ['SearchSeriesNode', 'SearchEpisodeNode', 'SearchTranscriptNode']):
            expectedNodeType = 'SearchSeriesNode'
        elif expectedNodeType == 'SearchSeriesNode':
            expectedNodeType = 'SearchEpisodeNode'
        elif expectedNodeType == 'SearchEpisodeNode':
            expectedNodeType = 'SearchTranscriptNode'
        elif (expectedNodeType == 'SearchResultsNode') and (nodeType in ['SearchCollectionNode', 'SearchClipNode']):
            expectedNodeType = 'SearchCollectionNode'
        elif (expectedNodeType == 'SearchCollectionNode') and ((nodeListPos == len(nodeData) - 1) and (nodeType in ['SearchClipNode'])):
            expectedNodeType = 'SearchClipNode'
        elif expectedNodeType == 'Node':
            expectedNodeType = 'Node'
        return expectedNodeType

    def Evaluate(self, node, nodeType, child, childData):
        allNoteNodeTypes = ['NoteNode', 'SeriesNoteNode', 'EpisodeNoteNode', 'TranscriptNoteNode', 'CollectionNoteNode', 'ClipNoteNode']

#        if child.IsOk():
#            print '"%s", %s, "%s", %s' % (node, nodeType, self.GetItemText(child), childData.nodetype)
#        else:
#            print '"%s", %s, last node entry' % (node, nodeType)
#        print child.IsOk()
#        if child.IsOk():
#            print '((',node > self.GetItemText(child), 'and '

        # We continue moving down the list of nodes if...
        #   ... we are not yet at the end of the list AND ...
        # ((we're not past our alpha place and (nodetypes are the same or (both are at least Notes)) or
        #  (we're dealing with a Note and we're not to the notes yet)) AND ...
        # (we don't have a Collection or we haven't started looking at Clips ) or
        # we've got a SearchCollection to position after the SearchSeries nodes
        result = child.IsOk() and \
                 (((node > self.GetItemText(child)) and \
                   (((nodeType == childData.nodetype)) or \
                    ((nodeType in allNoteNodeTypes) and (childData.nodetype in allNoteNodeTypes)))) or \
                  ((nodeType in allNoteNodeTypes) and not(childData.nodetype in allNoteNodeTypes))) or \
                 ((nodeType == 'ClipNode') and ((childData.nodetype == 'CollectionNode') or \
                                                (childData.nodetype == 'ClipNode'))) or \
                 ((nodeType == 'SearchCollectionNode') and (childData.nodetype == 'SearchSeriesNode')) or \
                 ((nodeType == 'SearchClipNode') and (childData.nodetype == 'SearchClipNode') and (True))
        # ******************************************************************************************************
        # IF THIS IS NOT ADEQUATE, True must be replaced by a comparison of SortOrders!!  BUT THIS MIGHT WORK!!!
        # ******************************************************************************************************

#         print '=', result
#         print

#        if (nodeType == 'SearchClipNode') and (childData.nodetype == 'SearchClipNode'):
#            print 'self.GetPyData(node)', childData

        return result
        
    def add_Node(self, nodeType, nodeData, nodeRecNum, nodeParent, expandNode = True, insertPos = None):
        """ This method is used to add nodes to the tree after it has been built.
            nodeType is the type of node to be added, and nodeData is a list that gives the tree structure
            that describes where the node should be added. """
        currentNode = self.GetRootItem()

        # print "Root node = %s" % self.GetItemText(currentNode)
        # print "nodeData =", nodeData
        # print 'nodeType =', nodeType

        # Having nodes and subnodes with the same name causes a variety of problems.  We need to track how far
        # down the tree branches we are to keep track of what object NodeTypes we should be working with.
        nodeListPos = 0
        if nodeType in ['SeriesRootNode', 'SeriesNode', 'EpisodeNode', 'TranscriptNode',
                        'SeriesNoteNode', 'EpisodeNoteNode', 'TranscriptNoteNode']:
            expectedNodeType = 'SeriesRootNode'
        elif nodeType in ['CollectionsRootNode', 'CollectionNode', 'ClipNode',
                          'CollectionNoteNode', 'ClipNoteNode']:
            expectedNodeType = 'CollectionsRootNode'
        elif nodeType in ['KeywordRootNode', 'KeywordGroupNode', 'KeywordNode', 'KeywordExampleNode']:
            expectedNodeType = 'KeywordRootNode'
        elif nodeType in ['SearchRootNode', 'SearchResultsNode', 'SearchSeriesNode', 'SearchEpisodeNode', 'SearchTranscriptNode', 'SearchCollectionNode', 'SearchClipNode']:
            expectedNodeType = 'SearchRootNode'

        # print 'expectedNodeType =', expectedNodeType
        # print 'nodeData = ', nodeData

        for node in nodeData:

            node = node.strip()

            # print "Looking for '%s'" % node
            # print "Current nodeListPos = %d, expectedNodeType = %s" % (nodeListPos, expectedNodeType)

            notDone = True
            (childNode, cookieItem) = self.GetFirstChild(currentNode)

            while notDone:

		if childNode.IsOk():
                    itemText = self.GetItemText(childNode).strip()
                    
                    # print "Looking in %s at %s for %s." % (self.GetItemText(currentNode), itemText, node)

                    # Let's get the child Node's Data
                    childNodeData = self.GetPyData(childNode)
                else:
                    itemText = ''
                    childNodeData = None
                    
                # print nodeType, childNode.IsOk()

                # To accept a node and climb on, the node text must match the text of the node being sought.
                # If the node being added is a Keyword Example Node, we also need to make sure that the node being
                # sought's Record Number matches the node being added's Record Number.  This is because it IS possible
                # to have two clips with the same name in different collections applied as examples of the same Keyword.

                # print 'NodeTypes:', nodeType, 
                # if childNode.IsOk():
                #     print childNodeData.nodetype
                # else:
                #     print 'childNode is not Ok.'

                # If this is a SearchResultsNode and there is at least one child, place the new entry above that first child.
                # This has the effect of putting Search Results nodes in Reverse Chronological Order.
                if (nodeType == 'SearchResultsNode') and childNode.IsOk():
                    insertPos = childNode

                # Complex comparison:
                #  1) is the childNode valid?
                #  2) does the child node's text match the next node in the nodelist?
                #  3) are the NodeTypes from compatible branches in the DB Tree?
                #  4) Is it a Keyword Example OR the correct record number
                if  (childNode.IsOk()) and \
                    \
                    (itemText == node) and \
                    \
                    (childNodeData.nodetype in expectedNodeType) and \
                    \
                    ((childNodeData.nodetype != 'KeywordExampleNode') or (childNodeData.recNum == nodeRecNum)):

                    # print "In '%s', '%s' = '%s'.  Climbing on." % (self.GetItemText(currentNode), itemText, node)
                    # print

                    # We've found the next node.  Increment the nodeListPos counter.
                    nodeListPos += 1
                    expectedNodeType = self.UpdateExpectedNodeType(expectedNodeType, nodeListPos, nodeData, nodeType)

                    currentNode = childNode
                    notDone = False
                elif (not childNode.IsOk()) or (childNode == self.GetLastChild(currentNode)) or \
                     ((expectedNodeType == 'SearchResultsNode') and childNode.IsOk()):

                    # print "Adding in '%s' to '%s'." % (node, self.GetItemText(currentNode))

                    if nodeListPos < len(nodeData) - 1:
                        
                        # print "This is not the last Node.  It is node %s of %s" % (node, nodeData)

                        # Let's get the current Node's Data
                        currentNodeData = self.GetPyData(currentNode)

                        # print "currentNode = %s, %s" % (self.GetItemText(currentNode), currentNodeData),

                        # We know what type of node is expected next, so we know what kind of node to add

                        # If the expected node is a Series...
                        if expectedNodeType == 'SeriesNode':
                            tempSeries = Series.Series(node)
                            currentRecNum = tempSeries.number

                        # If the expected node is a Episode...
                        elif expectedNodeType == 'EpisodeNode':
                            tempEpisode = Episode.Episode(series=self.GetItemText(currentNode).strip(), episode=node)
                            currentRecNum = tempEpisode.number

                        # If the expected node is a Transcript...
                        elif expectedNodeType == 'TranscriptNode':

                            print "ExpectedNodeType == 'TranscriptNode'.  This has not been coded!"

                        # If the expected node is a Collection...
                        elif expectedNodeType == 'CollectionNode':
                            tempCollection = Collection.Collection(node, currentNodeData.recNum)
                            currentRecNum = tempCollection.number

                        # If the expected node is a Clip...
                        elif expectedNodeType == 'ClipNode':

                            print "ExpectedNodeType == 'ClipNode'.  This has not been coded!"

                        # If the expected node is a Keyword Group...
                        elif expectedNodeType == 'KeywordGroupNode':
                            currentRecNum = 0

                        # If the expected node is a Keyword...
                        elif expectedNodeType == 'KeywordNode':

                            print "ExpectedNodeType == 'KeywordNode'.  This has not been coded!"

                        # If the expected node is a SearchSeries...
                        elif expectedNodeType == 'SearchSeriesNode':
                            tempSeries = Series.Series(node)
                            currentRecNum = tempSeries.number

                        # If the LAST node is a SearchEpisode...
                        elif expectedNodeType == 'SearchEpisodeNode':
                            tempEpisode = Episode.Episode(series=self.GetItemText(currentNode).strip(), episode=node)
                            currentRecNum = tempEpisode.number

                        # If the LAST node is a SearchTranscript...
                        elif expectedNodeType == 'SearchTranscriptNode':

                            print "ExpectedNodeType == 'SearchTranscriptNode'.  This has not been coded!"

                        # If the LAST node is a SearchCollection...
                        elif expectedNodeType == 'SearchCollectionNode':
                            tempCollection = Collection.Collection(node, currentNodeData.recNum)
                            currentRecNum = tempCollection.number

                        # If the LAST node is a SearchClip...
                        elif expectedNodeType == 'SearchClipNode':

                            print "ExpectedNodeType == 'SearchClipNode'.  This has not been coded!"

                        # The new node's parent record number will be the current node's record number
                        currentParent = currentNodeData.recNum

                    # If we ARE at the end of the Node List, we can use the values passed in by the calling routine
                    else:

                        # print "end of the Node List"
                        
                        expectedNodeType = nodeType
                        currentRecNum = nodeRecNum
                        currentParent = nodeParent

                    # print "Positioning in Tree...", insertPos, childNode.IsOk()

                    # We need to position new nodes in the proper place alphabetically and by nodetype.
                    # We can do this by setting the insertPos.  Note that we don't need to do this if
                    # we already have insertPos info based on Sort Order.
                    if (insertPos == None) and (childNode.IsOk()):

                        # Let's get the current Node's Data
                        currentNodeData = self.GetPyData(currentNode)

                        # print "nodetype = ", currentNodeData.nodetype, 'expectedNodeType = ', expectedNodeType
                        # print

                        # Get the first Child Node of the Current Node
                        (child, cookieVal) = self.GetFirstChild(currentNode)
                        
                        if child.IsOk():
                            childData = self.GetPyData(child)

                            if nodeListPos < len(nodeData) - 1:
                                nt = expectedNodeType
                            else:
                                nt = nodeType
                            
                            # print "Evaluate(%s, %s, %s, %s)" % (node, nt, self.GetItemText(child), childData)

                            while self.Evaluate(node, nt, child, childData):

                                (child, cookieVal) = self.GetNextChild(currentNode, cookieVal)
                                if child.IsOk():
                                    childData = self.GetPyData(child)
                                else:
                                    break

                            if child.IsOk():
                                insertPos = child

                    # If no insertPos is specified, ...
                    if insertPos == None:
                        # .. Add the new Node to the Tree at the end
                        newNode = self.AppendItem(currentNode, node)
                    # Otherwise ...
                    else:
                        # Get the first Child Node of the Current Node
                        (firstChild, cookieVal) = self.GetFirstChild(currentNode)
                        
                        if firstChild.IsOk():
                            # If our Insert Position is the First Child ...
                            if insertPos == firstChild:
                                # ... we need to "Prepend" the item to the parent's Nodes
                                newNode = self.PrependItem(currentNode, node)
                            # Otherwise ...
                            else:
                                # We want to insert BEFORE insertPos, not after it, so grab the Previous Sibling before doing the Insert!
                                insertPos = self.GetPrevSibling(insertPos)
                                # and then insert the item under the Parent, after the insertPos's Previous Sibling
                                newNode = self.InsertItem(currentNode, insertPos, node)
                        else:
                            newNode = self.AppendItem(currentNode, node)

                    # Give the new Node the appropriate Graphic
                    if (expectedNodeType == 'SeriesNode') or (expectedNodeType == 'SearchSeriesNode'):
                        self.set_image(newNode, "Series16")
                    elif (expectedNodeType == 'EpisodeNode') or (expectedNodeType == 'SearchEpisodeNode'):
                        self.set_image(newNode, "Episode16")
                    elif (expectedNodeType == 'TranscriptNode') or (expectedNodeType == 'SearchTranscriptNode'):
                        self.set_image(newNode, "Transcript16")
                    elif (expectedNodeType == 'CollectionNode') or (expectedNodeType == 'SearchCollectionNode'):
                        self.set_image(newNode, "Collection16")
                    elif (expectedNodeType == 'ClipNode') or (expectedNodeType == 'SearchClipNode') or (expectedNodeType == 'KeywordExampleNode'):
                        self.set_image(newNode, "Clip16")
                    elif expectedNodeType in ['NoteNode', 'SeriesNoteNode', 'EpisodeNoteNode', 'TranscriptNoteNode', 'CollectionNoteNode', 'ClipNoteNode', 'SearchNoteNode']:
                        self.set_image(newNode, "Note16")
                    elif expectedNodeType == 'KeywordGroupNode':
                        self.set_image(newNode, "KeywordGroup16")
                    elif expectedNodeType == 'KeywordNode':
                        self.set_image(newNode, "Keyword16")
                    elif expectedNodeType == 'SearchResultsNode':
                        self.set_image(newNode, "Search16")
                    else:
                      dlg = Dialogs.ErrorDialog(self, 'Undefined wxTreeCtrl.set_image() for nodeType %s in _DBTreeCtrl.add_Node()' % nodeType)
                      dlg.ShowModal()
                      dlg.Destroy()
                    # Create the Node Data and attach it to the Node
                    # If the expectedNodeType is ANY Note Node, we need to set it to NoteNode
                    if expectedNodeType  in ['NoteNode', 'SeriesNoteNode', 'EpisodeNoteNode', 'TranscriptNoteNode', 'CollectionNoteNode', 'ClipNoteNode']:
                        newNodeType = 'NoteNode'
                    else:
                        newNodeType = expectedNodeType
                    nodedata = _NodeData(nodetype=newNodeType, recNum=currentRecNum, parent=currentParent)
                    self.SetPyData(newNode, nodedata)
                    if expandNode:
                        self.Expand(currentNode)

                    # We've found the next node.  Increment the nodeListPos counter.
                    nodeListPos += 1

                    expectedNodeType = self.UpdateExpectedNodeType(expectedNodeType, nodeListPos, nodeData, nodeType)

                    currentNode = newNode
                    notDone = False

                (childNode, cookieItem) = self.GetNextChild(currentNode, cookieItem)
        wx.Yield()

    def select_Node(self, nodeData, nodeType):
        """ This method is used to select nodes in the tree.
            nodeData is a list that gives the tree structure that describes where the node should be selected. """

        currentNode = self.GetRootItem()

        # print "Root node = %s" % self.GetItemText(currentNode)
        # print "nodeData = ", nodeData

        # Having nodes and subnodes with the same name causes a variety of problems.  We need to track how far
        # down the tree branches we are to keep track of what object NodeTypes we should be working with.
        nodeListPos = 0
        if nodeType in ['SeriesRootNode', 'SeriesNode', 'EpisodeNode', 'TranscriptNode',
                        'SeriesNoteNode', 'EpisodeNoteNode', 'TranscriptNoteNode']:
            expectedNodeType = 'SeriesRootNode'
        elif nodeType in ['CollectionsRootNode', 'CollectionNode', 'ClipNode',
                          'CollectionNoteNode', 'ClipNoteNode']:
            expectedNodeType = 'CollectionsRootNode'
        elif nodeType in ['KeywordRootNode', 'KeywordGroupNode', 'KeywordNode', 'KeywordExampleNode']:
            expectedNodeType = 'KeywordRootNode'
        elif nodeType in ['SearchRootNode', 'SearchResultsNode', 'SearchSeriesNode', 'SearchEpisodeNode', 'SearchTranscriptNode', 'SearchCollectionNode', 'SearchClipNode']:
            expectedNodeType = 'SearchRootNode'

        for node in nodeData:

            node = node.strip()

            # print "Looking for %s" % node

            notDone = True
            (childNode, cookieItem) = self.GetFirstChild(currentNode)
            while notDone and (currentNode != None):
                itemText = self.GetItemText(childNode).strip()
                # if childNode.IsOk():
                #     print "Looking in %s at %s for %s." % (self.GetItemText(currentNode), itemText, node)

                # Let's get the child Node's Data
                childNodeData = self.GetPyData(childNode)

                # To accept a node and climb on, the node text must match the text of the node being sought.
                # If the node being added is a Keyword Example Node, we also need to make sure that the node being
                # sought's Record Number matches the node being added's Record Number.  This is because it IS possible
                # to have two clips with the same name in different collections applied as examples of the same Keyword.

                # Complex comparison:
                #  1) is the childNode valid?
                #  2) does the child node's text match the next node in the nodelist?
                #  3) are the NodeTypes from compatible branches in the DB Tree?
                #    a) Series, Episode, or Transcript
                #    b) Collection or Clip 
                #    c) Keyword Group, Keyword, or Keyword Example
                #    d) Search Results Series, Episode, or Transcript
                #    e) Search Results Collection or Clip
                #  4) Is it a Keyword Example OR the correct record number
                if  (childNode.IsOk()) and \
                    \
                    (itemText == node) and \
                    \
                    (childNodeData.nodetype in expectedNodeType):    # and \
#                    \
#                    ((childNodeData.nodetype != 'KeywordExampleNode') or (childNodeData.recNum == nodeRecNum)):

                    # print "In %s, %s = %s.  Climbing on." % (self.GetItemText(currentNode), itemText, node)

                    # We've found the next node.  Increment the nodeListPos counter.
                    nodeListPos += 1
                    expectedNodeType = self.UpdateExpectedNodeType(expectedNodeType, nodeListPos, nodeData, nodeType)

                    currentNode = childNode
                    notDone = False
                elif childNode == self.GetLastChild(currentNode):
                    dlg = Dialogs.ErrorDialog(self, 'Problem in _DBTreeCtrl.select_Node().\n"%s" not found for selection and display.' % node)
                    dlg.ShowModal()
                    dlg.Destroy()
                    currentNode = None
                    notDone = False

                if notDone:
                    (childNode, cookieItem) = self.GetNextChild(currentNode, cookieItem)
                
        if currentNode != None:

            # print "Need to select and display %s" % self.GetItemText(currentNode)

            self.SelectItem(currentNode)
            self.EnsureVisible(currentNode)
        return currentNode


    def delete_Node(self, nodeData, nodeType, exampleClipNum=0):
        """ This method is used to delete nodes to the tree after it has been built.
            nodeData is a list that gives the tree structure that describes where the node should be deleted. """
        currentNode = self.GetRootItem()

        # print "Root node = %s" % self.GetItemText(currentNode)
        # print "nodeData = ", nodeData, "of type", nodeType
        
        # Having nodes and subnodes with the same name causes a variety of problems.  We need to track how far
        # down the tree branches we are to keep track of what object NodeTypes we should be working with.
        nodeListPos = 0
        if nodeType in ['SeriesRootNode', 'SeriesNode', 'EpisodeNode', 'TranscriptNode',
                        'SeriesNoteNode', 'EpisodeNoteNode', 'TranscriptNoteNode']:
            expectedNodeType = 'SeriesRootNode'
        elif nodeType in ['CollectionsRootNode', 'CollectionNode', 'ClipNode',
                          'CollectionNoteNode', 'ClipNoteNode']:
            expectedNodeType = 'CollectionsRootNode'
        elif nodeType in ['KeywordRootNode', 'KeywordGroupNode', 'KeywordNode', 'KeywordExampleNode']:
            expectedNodeType = 'KeywordRootNode'
        elif nodeType in ['SearchRootNode', 'SearchResultsNode', 'SearchSeriesNode', 'SearchEpisodeNode', 'SearchTranscriptNode', 'SearchCollectionNode', 'SearchClipNode']:
            expectedNodeType = 'SearchRootNode'

        for node in nodeData:

            node = node.strip()

            # print "Looking for %s" % node
            
            notDone = True
            (childNode, cookieItem) = self.GetFirstChild(currentNode)

            while notDone and (currentNode != None):
                itemText = self.GetItemText(childNode).strip()

                # print "Looking in '%s' at '%s' for '%s'." % (self.GetItemText(currentNode), itemText, node)

                childNodeData = self.GetPyData(childNode)

                # print 'NodeTypes:', nodeType, 
                # if childNode.IsOk():
                #     print childNodeData.nodetype, expectedNodeType
                # else:
                #     print 'childNode is not Ok.'

                # To accept a node and climb on, the node text must match the text of the node being sought.
                # If the node being added is a Keyword Example Node, we also need to make sure that the node being
                # sought's Record Number matches the node being added's Record Number.  This is because it IS possible
                # to have two clips with the same name in different collections applied as examples of the same Keyword.

                # Complex comparison:
                #  1) is the childNode valid?
                #  2) does the child node's text match the next node in the nodelist?
                #  3) are the NodeTypes from compatible branches in the DB Tree?
                #    a) Series, Episode, or Transcript
                #    b) Collection or Clip 
                #    c) Keyword Group, Keyword, or Keyword Example
                #    d) Search Results Series, Episode, or Transcript
                #    e) Search Results Collection or Clip
                #  4) Is it a Keyword Example OR the correct record number
                if  (childNode.IsOk()) and \
                    \
                    (itemText == node) and \
                    \
                    (childNodeData.nodetype in expectedNodeType) and \
                    \
                    ((exampleClipNum == 0) or (childNodeData.nodetype != 'KeywordExampleNode') or (childNodeData.recNum == exampleClipNum)):

                    # print "In %s, %s = %s.  Climbing on." % (self.GetItemText(currentNode), itemText, node)
                    
                    # We've found the next node.  Increment the nodeListPos counter.
                    nodeListPos += 1
                    expectedNodeType = self.UpdateExpectedNodeType(expectedNodeType, nodeListPos, nodeData, nodeType)

                    currentNode = childNode
                    notDone = False
                elif childNode == self.GetLastChild(currentNode):
                    dlg = Dialogs.ErrorDialog(self, 'Problem in _DBTreeCtrl.delete_Node().\n"%s" not found for delete.' % node)
                    dlg.ShowModal()
                    dlg.Destroy()
                    currentNode = None
                    notDone = False
                (childNode, cookieItem) = self.GetNextChild(currentNode, cookieItem)

        if currentNode != None:

            # print "Need to delete %s" % self.GetItemText(currentNode)

            self.Delete(currentNode)
                    
                    
    def create_menus(self):
        """Create all the menu objects used in the tree control."""
        self.menu = {}          # Dictionary of menu references
        self.cmd_id_start = {}  # Dictionary of menu cmd_id starting points
        
        self.create_gen_menu()

        # Series Root Menu
        self.create_menu("series_root",
                        (_("Add Series"),),
                        self.OnSeriesRootCommand)

        # Series Menu
        self.create_menu("series",
                        (_("Paste"),
                         _("Add Episode"), _("Add Series Note"), _("Delete Series"), _("Keyword Usage Report"), _("Series Properties")),
                        self.OnSeriesCommand)

        # Episode Menu
        self.create_menu("episode",
                        (_("Paste"),
                         _("Add Transcript"), _("Add Episode Note"), _("Delete Episode"), _("Keyword Map"), _("Keyword Usage Report"), _("Episode Properties")),
                        self.OnEpisodeCommand)

        # Transcript Menu
        self.create_menu("transcript",
                         (_("Open"), _("Add Transcript Note"), _("Delete Transcript"), _("Transcript Properties")),
                         self.OnTranscriptCommand)

        # Collection Root Menu
        self.create_menu("coll_root",
                        (_("Add Collection"),),
                        self.OnCollRootCommand)

        # Collection Menu
        self.create_menu("collection",
                        (_("Cut"), _("Copy"), _("Paste"),
                         _("Add Clip"), _("Add Nested Collection"), _("Add Collection Note"),
                         _("Collection Summary Report"), _("Delete Collection"),
                         _("Keyword Usage Report"), _("Play All Clips"), _("Collection Properties")),
                        self.OnCollectionCommand)

        # Clip Menu
        self.create_menu("clip",
                        (_("Cut"), _("Copy"), _("Paste"),
                         _("Open"), _("Add Clip Note"), _("Delete Clip"),
                         _("Locate Clip in Episode"), _("Clip Properties")),
                        self.OnClipCommand)

        # Keywords Root Menu
        self.create_menu("kw_root",
                        (_("Add Keyword Group"), _("Keyword Management"),
                         _("Keyword Summary Report")),
                        self.OnKwRootCommand)

        # Keyword Group Menu
        self.create_menu("kw_group",
                        (_("Paste"),
                         _("Add Keyword"), _("Delete Keyword Group"), _("Keyword Summary Report")),
                        self.OnKwGroupCommand)

        # Keyword Menu
        self.create_menu("kw",
                        (_("Cut"), _("Copy"), _("Paste"),
                         _("Delete Keyword"), _("Keyword Properties")),
                        self.OnKwCommand)

        # Keyword Example Menu
        self.create_menu("kw_example",
                        (_("Open"), _("Locate this Clip"), _("Delete Keyword Example")),
                        self.OnKwExampleCommand)

        # Note Menu
        self.create_menu("note",
                        (_("Open"), _("Delete Note"), _("Note Properties")),
                        self.OnNoteCommand)
        
        # The Search Root Node menu
        self.create_menu("search",
                         (_("Clear All"), _("Search")),
                         self.OnSearchCommand)
        
        # The Search Results Node Menu
        self.create_menu("searchresults",
                         (_("Clear"), _("Convert to Collection"), _("Rename")),
                         self.OnSearchResultsCommand)
        
        # The Search Series Node Menu
        self.create_menu("searchseries",
                        (_("Drop from Search Result"), _("Keyword Usage Report")),
                        self.OnSearchSeriesCommand)
        
        # The Search Episode Node Menu
        self.create_menu("searchepisode",
                        (_("Drop from Search Result"), _("Keyword Map"), _("Keyword Usage Report")),
                        self.OnSearchEpisodeCommand)
        
        # The Search Transcript Node Menu
        self.create_menu("searchtranscript",
                         (_("Open"), _("Drop from Search Result")),
                         self.OnSearchTranscriptCommand)
        
        # The Search Collection Node Menu
        self.create_menu("searchcollection",
                        (_("Cut"), _("Copy"), _("Paste"),
                         _("Collection Summary Report"), _("Drop from Search Result"), _("Keyword Usage Report"),
                         _("Play All Clips"), _("Rename")),
                        self.OnSearchCollectionCommand)
        
        # The Search Clip Node Menu
        self.create_menu("searchclip",
                        (_("Cut"), _("Copy"), _("Paste"),
                         _("Open"), _("Drop for Search Result"), _("Locate Clip in Episode"), _("Rename")),
                        self.OnSearchClipCommand)


    def create_menu(self, name, items, handler):
        menu = wx.Menu()
        self.cmd_id_start[name] = self.cmd_id
        for item_s in items:
            menu.Append(self.cmd_id, item_s)
            wx.EVT_MENU(self, self.cmd_id, handler)
            self.cmd_id += 1
        self.menu[name] = menu

    def create_gen_menu(self):
        menu = wx.Menu()
        menu.Append(self.cmd_id, _("Update Database Window"))
        self.gen_menu = menu
        wx.EVT_MENU(self, self.cmd_id, self.refresh_tree)
        self.cmd_id += 1

    def OnSeriesRootCommand(self, evt):
        """Handle selections for root Series menu."""
        n = evt.GetId() - self.cmd_id_start["series_root"]
        
        if n == 0:      # Add Series
            self.parent.add_series()
#        elif n == 1:    # Update Database Window
#            self.refresh_tree()
        else:
            raise MenuIDError
 
 
    def OnSeriesCommand(self, evt):
        """Handle menu selections for Series objects."""
        n = evt.GetId() - self.cmd_id_start["series"]
       
        sel = self.GetSelection()
        selData = self.GetPyData(sel)
        series_name = self.GetItemText(sel)
        
        if n == 0:      # Paste
            # Open the Clipboard
            # wx.TheClipboard.Open()
            # specify the data formats to accept
            df = wx.CustomDataFormat('DataTreeDragData')
            # Specify the data object to accept data for this format
            cdo = wx.CustomDataObject(df)
            # Try to get the appropriate data from the Clipboard      
            success = wx.TheClipboard.GetData(cdo)
            # If we got appropriate data ...
            if success:
                # ... unPickle the data so it's in a usable format
                data = cPickle.loads(cdo.GetData())
                DragAndDropObjects.ProcessPasteDrop(self, data, sel, self.cutCopyInfo['action'])

        elif n == 1:    # Add Episode
            # Add an Episode
            episode_name = self.parent.add_episode(series_name)
            # If the Episode is successfully loaded ( != None) ...
            if episode_name != None:
                # Select the Episode in the Data Tree
                sel = self.select_Node((_('Series'), series_name, episode_name), 'EpisodeNode')
                # Automatically prompt to create a Transcript
                transcript_name = self.parent.add_transcript(series_name, episode_name)
                # If the Transcript is created ( != None) ...
                if transcript_name != None:
                    # Select the Transcript in the Data Tree
                    sel = self.select_Node((_('Series'), series_name, episode_name, transcript_name), 'TranscriptNode')
                    # Load the newly created Transcript
                    self.parent.ControlObject.LoadTranscript(series_name, episode_name, transcript_name)  # Load everything via the ControlObject
            
        elif n == 2:    # Add Note
            self.parent.add_note(seriesNum=selData.recNum)
            
        elif n == 3:    # Delete
            # Load the Selected Series
            series = Series.Series(selData.recNum)
            # Get user confirmation of the Series Delete request
            dlg = wx.MessageDialog(self, _('Are you sure you want to delete Series "%s" and all related Episodes, Transcripts and Notes?') % (self.GetItemText(sel)), _("Transana Confirmation"), style=wx.YES_NO | wx.ICON_QUESTION)
            result = dlg.ShowModal()
            dlg.Destroy()
            # If the user confirms the Delete Request...
            if result == wx.ID_YES:
                # Start by clearing all current objects
                self.parent.ControlObject.ClearAllWindows()
                # Try to delete the Series, initiating a Transaction
                delResult = series.db_delete(1)
                # If successful, remove the Series Node from the Database Tree
                if delResult:
                    # Get the full Node Branch by climbing it to one level above the root
                    nodeList = (self.GetItemText(sel),)
                    while (self.GetItemParent(sel) != self.GetRootItem()):
                        sel = self.GetItemParent(sel)
                        nodeList = (self.GetItemText(sel),) + nodeList
                        # print nodeList
                    # Call the DB Tree's delete_Node method.
                    self.delete_Node(nodeList, 'SeriesNode')
                
        elif n == 4:    # Keyword Usage Report
            KeywordUsageReport.KeywordUsageReport(seriesName = series_name)
            
        elif n == 5:    # Properties
            series = Series.Series()
            # FIXME: Gracefully handle when we can't load the series.
            # (yes, this can happen.  for example if another user changes
            # the name of it before the tree is refreshed.  then you'll get
            # a RecordNotFoundError.  Then we should auto-refresh.
            series.db_load_by_name(series_name)
            self.parent.edit_series(series)
            
        else:
            raise MenuIDError
 
 
    def OnEpisodeCommand(self, evt):
        """Handle menu selections for Episode objects."""
        n = evt.GetId() - self.cmd_id_start["episode"]
       
        sel = self.GetSelection()
        selData = self.GetPyData(sel)
        episode_name = self.GetItemText(sel)
        series_name = self.GetItemText(self.GetItemParent(sel))
        
        if n == 0:      # Paste
            # Open the Clipboard
            # wx.TheClipboard.Open()
            # specify the data formats to accept
            df = wx.CustomDataFormat('DataTreeDragData')
            # Specify the data object to accept data for this format
            cdo = wx.CustomDataObject(df)
            # Try to get the appropriate data from the Clipboard      
            success = wx.TheClipboard.GetData(cdo)
            # If we got appropriate data ...
            if success:
                # ... unPickle the data so it's in a usable format
                data = cPickle.loads(cdo.GetData())
                DragAndDropObjects.ProcessPasteDrop(self, data, sel, self.cutCopyInfo['action'])
            
        elif n == 1:    # Add Transcript
            # Add the Transcript
            transcript_name = self.parent.add_transcript(series_name, episode_name)
            # If the Transcript is created ( != None) ...
            if transcript_name != None:
                # Select the Transcript in the Data Tree
                sel = self.select_Node((_('Series'), series_name, episode_name, transcript_name), 'TranscriptNode')
                # Load the newly created Transcript
                self.parent.ControlObject.LoadTranscript(series_name, episode_name, transcript_name)  # Load everything via the ControlObject

        elif n == 2:    # Add Note
            self.parent.add_note(episodeNum=selData.recNum)

        elif n == 3:    # Delete
            # Load the Selected Episode
            episode = Episode.Episode(selData.recNum)
            # Get user confirmation of the Episode Delete request
            dlg = wx.MessageDialog(self, _('Are you sure you want to delete Episode "%s" and all related Transcripts and Notes?\n(Please note that the video file associated with this Episode will not be deleted.)') % (self.GetItemText(sel)), _("Transana Confirmation"), style=wx.YES_NO | wx.ICON_QUESTION)
            result = dlg.ShowModal()
            dlg.Destroy()
            # If the user confirms the Delete Request...
            if result == wx.ID_YES:
                # Start by clearing all current objects
                self.parent.ControlObject.ClearAllWindows()
                # Try to delete the Episode, initiating a Transaction
                delResult = episode.db_delete(1)
                # If successful, remove the Episode Node from the Database Tree
                if delResult:
                    # Get the full Node Branch by climbing it to one level above the root
                    nodeList = (self.GetItemText(sel),)
                    while (self.GetItemParent(sel) != self.GetRootItem()):
                        sel = self.GetItemParent(sel)
                        nodeList = (self.GetItemText(sel),) + nodeList
                        # print nodeList
                    # Call the DB Tree's delete_Node method.
                    self.delete_Node(nodeList, 'EpisodeNode')
                
        elif n == 4:    # Keyword Map Report
            self.KeywordMapReport(series_name, episode_name)

        elif n == 5:    # Keyword Usage Report
            KeywordUsageReport.KeywordUsageReport(seriesName = series_name, episodeName = episode_name)

        elif n == 6:    # Properties
            series_name = self.GetItemText(self.GetItemParent(sel))
            episode = Episode.Episode()
            # FIXME: Gracefully handle when we can't load the Episode.
            episode.db_load_by_name(series_name, episode_name)
            self.parent.edit_episode(episode)

        else:
            raise MenuIDError

    def OnTranscriptCommand(self, evt):
        """ Handle menuy selections for Transcript menu """
        n = evt.GetId() - self.cmd_id_start["transcript"]
       
        sel = self.GetSelection()
        selData = self.GetPyData(sel)
        transcript_name = self.GetItemText(sel)
        
        if n == 0:      # Open
            self.OnItemActivated(evt)                            # Use the code for double-clicking the Transcript

        elif n == 1:    # Add Note
            self.parent.add_note(transcriptNum=selData.recNum)

        elif n == 2:    # Delete
            # Load the Selected Transcript
            transcript = Transcript.Transcript(selData.recNum)
            # Get user confirmation of the Transcript Delete request
            dlg = wx.MessageDialog(self, _('Are you sure you want to delete Transcript "%s" and all related Notes?') % (self.GetItemText(sel)), _("Transana Confirmation"), style=wx.YES_NO | wx.ICON_QUESTION)
            result = dlg.ShowModal()
            dlg.Destroy()
            # If the user confirms the Delete Request...
            if result == wx.ID_YES:
                # Start by clearing all current objects
                self.parent.ControlObject.ClearAllWindows()
                # Try to delete the Transcript, initiating a Transaction
                delResult = transcript.db_delete(1)
                # If successful, remove the Transcript Node from the Database Tree
                if delResult:
                    # Get the full Node Branch by climbing it to one level above the root
                    nodeList = (self.GetItemText(sel),)
                    while (self.GetItemParent(sel) != self.GetRootItem()):
                        sel = self.GetItemParent(sel)
                        nodeList = (self.GetItemText(sel),) + nodeList
                        # print nodeList
                    # Call the DB Tree's delete_Node method.
                    self.delete_Node(nodeList, 'TranscriptNode')

        elif n == 3:    # Properties
            series_name = self.GetItemText(self.GetItemParent(self.GetItemParent(sel)))
            episode_name = self.GetItemText(self.GetItemParent(sel))
            episode = Episode.Episode()
            episode.db_load_by_name(series_name, episode_name)
            transcript = Transcript.Transcript(transcript_name, episode.number)
            self.parent.edit_transcript(transcript)

        else:
            raise MenuIDError
         
    def OnCollRootCommand(self, evt):
        """Handle selections for root Collection menu."""
        n = evt.GetId() - self.cmd_id_start["coll_root"]

        if n == 0:      # Add Collection
            self.parent.add_collection(0)

#        elif n == 1:    # Update Database Window
#            self.refresh_tree()

        else:
            raise MenuIDError
    
    def OnCollectionCommand(self, evt):
        """Handle menu selections for Collection objects."""
        n = evt.GetId() - self.cmd_id_start["collection"]
        
        sel = self.GetSelection()
        selData = self.GetPyData(sel)
        coll_name = self.GetItemText(sel)
        parent_num = self.GetPyData(sel).parent
        
        
        if n == 0:      # Cut
            self.cutCopyInfo['action'] = 'Move'    # Functionally, "Cut" is the same as Drag/Drop Move
            self.cutCopyInfo['sourceItem'] = sel
            self.OnCutCopyBeginDrag(evt)

        elif n == 1:    # Copy
            self.cutCopyInfo['action'] = 'Copy'
            self.cutCopyInfo['sourceItem'] = sel
            self.OnCutCopyBeginDrag(evt)

        elif n == 2:    # Paste
            # Open the Clipboard
            # wx.TheClipboard.Open()
            # specify the data formats to accept.
            #   Our data could be a DataTreeDragData object if the source is the Database Tree
            dfNode = wx.CustomDataFormat('DataTreeDragData')
            #   Our data could be a ClipDragDropData object if the source is the Transcript (clip creation)
            dfClip = wx.CustomDataFormat('ClipDragDropData')

            # Specify the data object to accept data for these formats
            #   A DataTreeDragData object will populate the cdoNode object
            cdoNode = wx.CustomDataObject(dfNode)
            #   A ClipDragDropData object will populate the cdoClip object
            cdoClip = wx.CustomDataObject(dfClip)

            # Create a composite Data Object from the object types defined above
            cdo = wx.DataObjectComposite()
            cdo.Add(cdoNode)
            cdo.Add(cdoClip)

            # Try to get data from the Clipboard
            success = wx.TheClipboard.GetData(cdo)

            # Close the Clipboard
            # wx.TheClipboard.Close()

            # If the data in the clipboard is in an appropriate format ...
            if success:
                # ... unPickle the data so it's in a usable form
                # First, let's try to get the DataTreeDragData object
                try:
                    data = cPickle.loads(cdoNode.GetData())
                except:
                    data = None
                    # If this fails, that's okay
                    pass

                # Then lets try to get a ClipDragDropData object
                try:
                    data2 = cPickle.loads(cdoClip.GetData())
                except:
                    data2 = None
                    # If this fails, that's okay
                    pass

                # If we don't get the DataTreeDragData object, we need to substitute the ClipDragDropData item
                if data == None:
                    data = data2
                    
                if type(data) == type(DragAndDropObjects.ClipDragDropData()):
                    DragAndDropObjects.CreateClip(data, selData, self, sel)
                else:
                    DragAndDropObjects.ProcessPasteDrop(self, data, sel, self.cutCopyInfo['action'])

        elif n == 3:    # Add Clip
            self.parent.add_clip(coll_name)

        elif n == 4:    # Add Nested Collection
            coll = Collection.Collection(coll_name, parent_num)
            self.parent.add_collection(coll.number)

        elif n == 5:    # Add Note
            self.parent.add_note(collectionNum=selData.recNum)

        elif n == 6:    # Collection Summary Report
            CollectionSummaryReport.CollectionSummaryReport(self, sel)       # (selData, coll_name)

        elif n == 7:    # Delete
            # Load the Selected Collection
            collection = Collection.Collection(selData.recNum)
            # Get user confirmation of the Collection Delete request
            dlg = wx.MessageDialog(self, _('Are you sure you want to delete Collection "%s" and all related Nested Collections, Clips and Notes?') % (self.GetItemText(sel)), _("Transana Confirmation"), style=wx.YES_NO | wx.ICON_QUESTION)
            result = dlg.ShowModal()
            dlg.Destroy()
            # If the user confirms the Delete Request...
            if result == wx.ID_YES:
                # Start by clearing all current objects
                self.parent.ControlObject.ClearAllWindows()
                # If the delete is successful, we will need to remove all Keyword Examples for all Clips that get deleted.
                # Let's get a  list of those Keyword Examples before we do anything.
                kwExamples = DBInterface.list_all_keyword_examples_for_all_clips_in_a_collection(selData.recNum)
                # Try to delete the Collection, initiating a Transaction
                delResult = collection.db_delete(1)
                # If successful, remove the Collection Node from the Database Tree
                if delResult:
                    # We need to remove the Keyword Examples from the Database Tree before we remove the Collection Node.
                    # Deleting all these ClipKeyword records needs to remove Keyword Example Nodes in the DBTree.
                    # That needs to be done here in the User Interface rather than in the Clip Object, as that is
                    # a user interface issue.  The Clip Record and the Clip Keywords Records get deleted, but
                    # the user interface does not get cleaned up by deleting the Clip Object.
                    for (kwg, kw, clipNum, clipID) in kwExamples:
                        self.delete_Node((_("Keywords"), kwg, kw, clipID), 'KeywordExampleNode', exampleClipNum = clipNum)
                    
                    # Get the full Node Branch by climbing it to one level above the root
                    nodeList = (self.GetItemText(sel),)
                    while (self.GetItemParent(sel) != self.GetRootItem()):
                        sel = self.GetItemParent(sel)
                        nodeList = (self.GetItemText(sel),) + nodeList
                        # print nodeList
                    # Call the DB Tree's delete_Node method.
                    self.delete_Node(nodeList, 'CollectionNode')

        elif n == 8:    # Keyword Usage Report
            coll = Collection.Collection(coll_name, parent_num)
            KeywordUsageReport.KeywordUsageReport(collection = coll)

        elif n == 9:    # Play All Clips
            # self.parent.ControlObject.ClearAllWindows()
            coll = Collection.Collection(coll_name, parent_num)
            # Play All Clips takes the current Collection and the ControlObject as parameters.
            # (The ControlObject is owned not by the _DBTreeCtrl but by its parent)
            PlayAllClips.PlayAllClips(collection=coll, controlObject=self.parent.ControlObject)
            # Return the Data Window to the Database Tab
            self.parent.ControlObject.ShowDataTab(0)
            # Let's Update the Play State, so that if we've been in Presentation Mode, the screen will be reset.
            self.parent.ControlObject.UpdatePlayState(TransanaConstants.MEDIA_PLAYSTATE_STOP)
            # Let's clear all the Windows, since we don't want to stay in the last Clip played.
            self.parent.ControlObject.ClearAllWindows()

        elif n == 10:    # Properties
            # FIXME: Gracefully handle when we can't load the Collection.
            coll = Collection.Collection(coll_name, parent_num)
            self.parent.edit_collection(coll)

        else:
            raise MenuIDError

    def OnClipCommand(self, evt):
        """Handle selections for the Clip menu."""
        n = evt.GetId() - self.cmd_id_start["clip"]
        
        sel = self.GetSelection()
        selData = self.GetPyData(sel)
        clip_name = self.GetItemText(sel)
        coll_name = self.GetItemText(self.GetItemParent(sel))
        coll_parent_num = self.GetPyData(self.GetItemParent(sel)).parent
        
        if n == 0:      # Cut
            self.cutCopyInfo['action'] = 'Move'    # Functionally, "Cut" is the same as Drag/Drop Move
            self.cutCopyInfo['sourceItem'] = sel
            self.OnCutCopyBeginDrag(evt)

        elif n == 1:    # Copy
            self.cutCopyInfo['action'] = 'Copy'
            self.cutCopyInfo['sourceItem'] = sel
            self.OnCutCopyBeginDrag(evt)

        elif n == 2:    # Paste
            # Open the Clipboard
            # wx.TheClipboard.Open()
            # specify the data formats to accept.
            #   Our data could be a DataTreeDragData object if the source is the Database Tree
            dfNode = wx.CustomDataFormat('DataTreeDragData')
            #   Our data could be a ClipDragDropData object if the source is the Transcript (clip creation)
            dfClip = wx.CustomDataFormat('ClipDragDropData')

            # Specify the data object to accept data for these formats
            #   A DataTreeDragData object will populate the cdoNode object
            cdoNode = wx.CustomDataObject(dfNode)
            #   A ClipDragDropData object will populate the cdoClip object
            cdoClip = wx.CustomDataObject(dfClip)

            # Create a composite Data Object from the object types defined above
            cdo = wx.DataObjectComposite()
            cdo.Add(cdoNode)
            cdo.Add(cdoClip)

            # Try to get data from the Clipboard
            success = wx.TheClipboard.GetData(cdo)

            # Close the Clipboard
            # wx.TheClipboard.Close()

            # If the data in the clipboard is in an appropriate format ...
            if success:
                # ... unPickle the data so it's in a usable form
                # First, let's try to get the DataTreeDragData object
                try:
                    data = cPickle.loads(cdoNode.GetData())
                except:
                    data = None
                    # If this fails, that's okay
                    pass

                # Let's also try to get the ClipDragDropData object
                try:
                    data2 = cPickle.loads(cdoClip.GetData())
                except:
                    data2 = None
                    # If this fails, that's okay
                    pass

                # if we didn't get the DataTreeDragData object, we need to substitute the ClipDragDropData object
                if data == None:
                    data = data2
                    
                if type(data) == type(DragAndDropObjects.ClipDragDropData()):
                    DragAndDropObjects.CreateClip(data, selData, self, sel)
                else:
                    DragAndDropObjects.ProcessPasteDrop(self, data, sel, self.cutCopyInfo['action'])

        elif n == 3:    # Open
            self.OnItemActivated(evt)                            # Use the code for double-clicking the Clip

        elif n == 4:    # Add Note
            self.parent.add_note(clipNum=selData.recNum)

        elif n == 5:    # Delete
            # Load the Selected Clip
            clip = Clip.Clip(selData.recNum)
            # Get user confirmation of the Clip Delete request
            dlg = wx.MessageDialog(self, _('Are you sure you want to delete Clip "%s" and all related Notes?') % (self.GetItemText(sel)), _("Transana Confirmation"), style=wx.YES_NO | wx.ICON_QUESTION)
            result = dlg.ShowModal()
            dlg.Destroy()
            # If the user confirms the Delete Request...
            if result == wx.ID_YES:
                # Start by clearing all current objects
                self.parent.ControlObject.ClearAllWindows()

                # Determine what Keyword Examples exist for the specified Clip so that they can be removed from the
                # Database Tree if the delete succeeds.  We must do that first, as the Clips themselves and the
                # ClipKeywords Records will be deleted later!
                kwExamples = DBInterface.list_all_keyword_examples_for_a_clip(selData.recNum)
            
                # Try to delete the Clip, initiating a Transaction
                delResult = clip.db_delete(1)
                # If successful, remove the Clip Node from the Database Tree
                if delResult:
                    # Get a temporary Selection Pointer
                    tempSel = sel
                    # Get the full Node Branch by climbing it to one level above the root
                    nodeList = (self.GetItemText(tempSel),)
                    while (self.GetItemParent(tempSel) != self.GetRootItem()):
                        tempSel = self.GetItemParent(tempSel)
                        nodeList = (self.GetItemText(tempSel),) + nodeList
                        # print nodeList

                    # Deleting all these ClipKeyword records needs to remove Keyword Example Nodes in the DBTree.
                    # That needs to be done here in the User Interface rather than in the Clip Object, as that is
                    # a user interface issue.  The Clip Record and the Clip Keywords Records get deleted, but
                    # the user interface does not get cleaned up by deleting the Clip Object.
                    for (kwg, kw, clipNum, clipID) in kwExamples:
                        self.delete_Node((_("Keywords"), kwg, kw, clipID), 'KeywordExampleNode', exampleClipNum = clipNum)

                    # Call the DB Tree's delete_Node method.
                    self.delete_Node(nodeList, 'ClipNode')

        elif n == 6:    # Locate Clip in Episode
            # Load the Clip
            clip = Clip.Clip(clip_name, coll_name, coll_parent_num)

            try:
                episode = Episode.Episode(clip.episode_num)

                if clip.transcript_num != 0:
                    transcript = Transcript.Transcript(clip.transcript_num)
                else:
                    transcriptList = DBInterface.list_transcripts(episode.series_id, episode.id)
                    if len(transcriptList) == 1:
                        transcript = Transcript.Transcript(transcriptList[0][0])
                    else:
                        strList = []
                        for (transcriptNum, transcriptID, episodeNum) in transcriptList:
                            strList.append(transcriptID)
                        dlg = wx.SingleChoiceDialog(self, _('Transana cannot identify the Transcript where this clip originated.\nPlease select the Transcript that was used to create this Clip.'), 'Transana Information', strList, wx.OK | wx.CANCEL)
                        if dlg.ShowModal() == wx.ID_OK:
                            transcript = Transcript.Transcript(dlg.GetStringSelection(), episode.number)
                        else:
                            raise RecordNotFoundError ('Transcript', 0)

                if self.parent.ControlObject != None:
                    self.parent.ControlObject.LoadTranscript(episode.series_id, episode.id, transcript.id)
                    self.parent.ControlObject.SetVideoSelection(clip.clip_start, clip.clip_stop)
            except:
                (extype, value, traceback) = sys.exc_info()
                # print "DatabaseTreeTab.OnClipCommand:  Exception raised.\nType = %s\nValue = %s\nTraceback = %s" % (extype, value, traceback)
                dlg = Dialogs.ErrorDialog(self, _('The Transcript this Clip was created from cannot be loaded.\nMost likely, the transcript has been deleted.'))
                result = dlg.ShowModal()
                dlg.Destroy()
                
            

        elif n == 7:    # Properties
            clip = Clip.Clip(clip_name, coll_name, coll_parent_num)
            self.parent.edit_clip(clip)

        else:
            raise MenuIDError

    def OnNoteCommand(self, evt):
        """Handle selections for the Note menu."""
        n = evt.GetId() - self.cmd_id_start["note"]
        
        sel = self.GetSelection()
        note_name = self.GetItemText(sel)
        selData = self.GetPyData(sel)
        
        if n == 0:      # Open
            self.OnItemActivated(evt)                            # Use the code for double-clicking the Note

        elif n == 1:    # Delete
            # Load the Selected Note
            note = Note.Note(selData.recNum)
            # Get user confirmation of the Note Delete request
            dlg = wx.MessageDialog(self, _('Are you sure you want to delete Note "%s"?') % (self.GetItemText(sel)), _("Transana Confirmation"), style=wx.YES_NO | wx.ICON_QUESTION)
            result = dlg.ShowModal()
            dlg.Destroy()
            # If the user confirms the Delete Request...
            if result == wx.ID_YES:
                # Try to delete the Note.  There is no need to initiate a Transaction for deleting a Note.
                delResult = note.db_delete(0)
                # If successful, remove the Note Node from the Database Tree
                if delResult:
                    # Get the full Node Branch by climbing it to one level above the root
                    nodeList = (self.GetItemText(sel),)
                    while (self.GetItemParent(sel) != self.GetRootItem()):
                        sel = self.GetItemParent(sel)
                        nodeList = (self.GetItemText(sel),) + nodeList
                        # print nodeList
                    # Call the DB Tree's delete_Node method.
                    # To climb the DBTree properly, we need to provide the note's PARENT's NodeType along with the NodeNode indication
                    noteParentNodeType = self.GetPyData(self.GetItemParent(self.GetSelection())).nodetype
                    if noteParentNodeType == 'SeriesNode':
                        noteNodeType = 'SeriesNoteNode'
                    elif noteParentNodeType == 'EpisodeNode':
                        noteNodeType = 'EpisodeNoteNode'
                    elif noteParentNodeType == 'TranscriptNode':
                        noteNodeType = 'TranscriptNoteNode'
                    elif noteParentNodeType == 'CollectionNode':
                        noteNodeType = 'CollectionNoteNode'
                    elif noteParentNodeType == 'ClipNode':
                        noteNodeType = 'ClipNoteNode'
                    self.delete_Node(nodeList, noteNodeType)

        elif n == 2:    # Properties
            note = Note.Note(selData.recNum)
            self.parent.edit_note(note)

        else:
            raise MenuIDError

    def OnKwRootCommand(self, evt):
        """Handle selections for the root Keyword group menu."""
        n = evt.GetId() - self.cmd_id_start["kw_root"]
        # Get the current selection
        sel = self.GetSelection()

        if n == 0:      # Add KW group
            # Get list of keyword group names in the tree.
            # The database may not contain everything in the tree due to the
            # database structure (keyword groups are a field of keyword
            # records, and dont have a record in itself).
            kwg_names = []
            for kw in self.kwgroups[1:]:        # skip 'Keywords' node @ 0
                kwg_names.append(self.GetItemText(kw))
     
            kwg = Dialogs.add_kw_group_ui(self, kwg_names)
            if kwg:
                nodeData = (_('Keywords'), kwg)
                # Add the new Keyword Group to the data tree
                self.add_Node('KeywordGroupNode', nodeData, 0, 0)

                # Since we've just inserted a new Keyword Group, we need to rebuild the self.kwgroups data structure.
                # This data structure is used to ensure that empty keyword groups still show up in the Keyword Properties dialog.
                # Initialize keyword groups to an empty list
                self.kwgroups = []
                # The "Keywords" node itself is always item 0 in the node list
                kwg_root = self.select_Node((_("Keywords"),), 'KeywordRootNode')
                self.kwgroups.append(kwg_root)
                (child, cookieVal) = self.GetFirstChild(kwg_root)
                while child.IsOk():
                    self.kwgroups.append(child)
                    (child, cookieVal) = self.GetNextChild(kwg_root, cookieVal)

        elif n == 1:    # KW Management
            # Call up the Keyword Management dialog
            KWManager.KWManager(self)
            # Refresh the Keywords Node to show the changes that were made
            self.refresh_kwgroups_node()

        elif n == 2:    # Keyword Summary Report
            if self.ItemHasChildren(sel):
                KeywordSummaryReport.KeywordSummaryReport()
            else:
                # Display the Error Message
                dlg = Dialogs.ErrorDialog(None, _('The requested Keyword Summary Report contains no data to display.'))
                dlg.ShowModal()
                dlg.Destroy()

#        elif n == 3:    # Update Database Window
#            self.refresh_tree()

        else:
            raise MenuIDError
  
    def OnKwGroupCommand(self, evt):
        """Handle selections for the root Keyword group menu."""
        n = evt.GetId() - self.cmd_id_start["kw_group"]
        
        # Get a reference to the KW Group node
        sel = self.GetSelection()
        kwg_name = self.GetItemText(sel)
        
        if n == 0:      # Paste
            # Open the Clipboard
            # wx.TheClipboard.Open()
            # specify the data formats to accept
            df = wx.CustomDataFormat('DataTreeDragData')
            # Specify the data object to accept data for this format
            cdo = wx.CustomDataObject(df)
            # Try to get the appropriate data from the Clipboard      
            success = wx.TheClipboard.GetData(cdo)
            # If we got appropriate data ...
            if success:
                # ... unPickle the data so it's in a usable format
                data = cPickle.loads(cdo.GetData())
                DragAndDropObjects.ProcessPasteDrop(self, data, sel, self.cutCopyInfo['action'])

        elif n == 1:    # Add Keyword
            self.parent.add_keyword(kwg_name)

        elif n == 2:    # Delete this keyword group
            msg = _('Are you sure you want to delete Keyword Group "%s", all of its keywords, and all instances of those keywords from the Clips?') % kwg_name
            id = wx.MessageDialog(self, msg, _("Transana Confirmation"), \
                        wx.YES | wx.NO | wx.CENTRE | wx.ICON_QUESTION).ShowModal()
            if id == wx.ID_YES:
                # Start by clearing all current objects
                self.parent.ControlObject.ClearAllWindows()
                # Delete the Keyword group
                DBInterface.delete_keyword_group(kwg_name)
                # We maintain a list of keyword groups so that empty ones don't get lost.  We need to remove the deleted keyword group form 
                # this list as well
                self.kwgroups.remove(sel)
                # Remove the Keyword Group from the tree
                self.Delete(sel)

        elif n == 3:    # Keyword Summary Report
            KeywordSummaryReport.KeywordSummaryReport(kwg_name)

        else:
            raise MenuIDError
 
    def OnKwCommand(self, evt):
        """Handle selections for the Keyword menu."""
        n = evt.GetId() - self.cmd_id_start["kw"]
        
        sel = self.GetSelection()
        kw_group = self.GetItemText(self.GetItemParent(sel))
        kw_name = self.GetItemText(sel)
        
        if n == 0:      # Cut
            self.cutCopyInfo['action'] = 'Move'    # Functionally, "Cut" is the same as Drag/Drop Move
            self.cutCopyInfo['sourceItem'] = sel
            self.OnCutCopyBeginDrag(evt)

        elif n == 1:    # Copy
            self.cutCopyInfo['action'] = 'Copy'
            self.cutCopyInfo['sourceItem'] = sel
            self.OnCutCopyBeginDrag(evt)

        elif n == 2:    # Paste
            # Open the Clipboard
            # wx.TheClipboard.Open()
            # specify the data formats to accept
            df = wx.CustomDataFormat('DataTreeDragData')
            # Specify the data object to accept data for this format
            cdo = wx.CustomDataObject(df)
            # Try to get the appropriate data from the Clipboard      
            success = wx.TheClipboard.GetData(cdo)
            # If we got appropriate data ...
            if success:
                # ... unPickle the data so it's in a usable format
                data = cPickle.loads(cdo.GetData())
                DragAndDropObjects.ProcessPasteDrop(self, data, sel, self.cutCopyInfo['action'])

        elif n == 3:    # Delete this keyword
            msg = _('Are you sure you want to delete Keyword "%s : %s" and all instances of it from the Clips?') % (kw_group, kw_name)
            id = wx.MessageDialog(self, msg, _("Transana Confirmation"), \
                        wx.YES | wx.NO | wx.CENTRE | wx.ICON_QUESTION).ShowModal()
            if id == wx.ID_YES:
                # Start by clearing all current objects
                self.parent.ControlObject.ClearAllWindows()
                # Delete teh Keyword
                DBInterface.delete_keyword(kw_group, kw_name)
                self.Delete(sel)

        elif n == 4:    # Keyword Properties
            kw = Keyword.Keyword(kw_group, kw_name)
            self.parent.edit_keyword(kw)

        else:
            raise MenuIDError

    def OnKwExampleCommand(self, evt):
        n = evt.GetId() - self.cmd_id_start["kw_example"]

        sel = self.GetSelection()
        selData = self.GetPyData(sel)

        if n == 0:      # Open
            self.OnItemActivated(evt)                            # Use the code for double-clicking the Keyword Example

        elif n == 1:    # Locate this Clip
            clipname = self.GetItemText(sel)                    # Capture Clip Name
            tempClip = Clip.Clip(selData.recNum)
            tempCollection = Collection.Collection(tempClip.collection_num)
            collectionList = [tempCollection.id]                     # Initialize a List
            while tempCollection.parent != 0:
                tempCollection = Collection.Collection(tempCollection.parent)
                collectionList.insert(0, tempCollection.id)
            nodeList = [_('Collections')] + collectionList + [clipname]
            self.select_Node(nodeList, 'ClipNode')
            
        elif n == 2:    # Delete
            kwg = self.GetItemText(self.GetItemParent(self.GetItemParent(sel)))
            kw = self.GetItemText(self.GetItemParent(sel))
            # Get user confirmation of the Keyword Example Add request
            dlg = wx.MessageDialog(self, _('Do you want to remove Clip "%s" as an example of Keyword "%s:%s"?') % (self.GetItemText(sel), kwg, kw), _("Transana Confirmation"), style=wx.YES_NO | wx.ICON_QUESTION)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
               DBInterface.SetKeywordExampleStatus(kwg, kw, selData.recNum, 0)
               nodeList = ('Keywords', kwg, kw, self.GetItemText(sel))
               # Call the DB Tree's delete_Node method.  Include the Clip Record Number so the correct Clip entry will be removed.
               self.delete_Node(nodeList, 'KeywordExampleNode', selData.recNum)
            
    def OnSearchCommand(self, event):
        """Handle selections for the Search menu."""
        n = event.GetId() - self.cmd_id_start["search"]
        sel = self.GetSelection()

        if n == 0:      # Clear All
            # Delete all child nodes
            self.DeleteChildren(sel)
            # reset the Search Counter
            self.searchCount = 1
            
        elif n == 1:    # Search
            # Process the Search Request
            search = ProcessSearch.ProcessSearch(self, self.searchCount)
            # Get the new searchCount Value (which may or may not be changed)
            self.searchCount = search.GetSearchCount()
            self.EnsureVisible(sel)
            
#        elif n == 2:    # Update Database Window
#            self.refresh_tree()
            
        else:
            raise MenuIDError

    def OnSearchResultsCommand(self, event):
        """Handle selections for the Search Results menu."""
        n = event.GetId() - self.cmd_id_start["searchresults"]
        sel = self.GetSelection()

        if n == 0:      # Clear 
            # Delete the node
            self.Delete(sel)
            
        elif n == 1:    # Convert to Collection
            # Get the data associated with the selected item
            sel_data = self.GetPyData(sel)
            # Convert the Search Result to a Collection
            if self.ConvertSearchToCollection(sel, sel_data):
                # Finally, if the Search result is converted, remove the converted Node
                # from the Search Results.
                self.delete_Node((_('Search'), self.GetItemText(sel)), 'SearchResultsNode')
            
        elif n == 2:    # Rename
            self.EditLabel(sel)
            
        else:
            raise MenuIDError

    def OnSearchSeriesCommand(self, evt):
        """Handle menu selections for Search Series objects."""
        n = evt.GetId() - self.cmd_id_start["searchseries"]
        sel = self.GetSelection()
        
        if n == 0:        # Drop for Search Results
            self.DropSearchResult(sel)
            
        elif n == 1:      # Keyword Usage Report
            KeywordUsageReport.KeywordUsageReport(searchSeries=sel, treeCtrl=self)

        else:
            raise MenuIDError
 
 
    def OnSearchEpisodeCommand(self, evt):
        """Handle menu selections for Search Episode objects."""
        n = evt.GetId() - self.cmd_id_start["searchepisode"]
        sel = self.GetSelection()
        episode_name = self.GetItemText(sel)
        series_name = self.GetItemText(self.GetItemParent(sel))
        
        if n == 0:      # Drop for Search Results
            self.DropSearchResult(sel)

        elif n == 1:      # Keyword Map Report
            self.KeywordMapReport(series_name, episode_name)
            
        elif n == 2:    # Keyword Usage Report
            msg = _('Please note that even though you are requesting this report based on Search Results, the data in \nthe report includes only Clips that are in Collections.  It does not include Search Results Clips.')
            infodlg = Dialogs.InfoDialog(self.parent, msg)
            infodlg.ShowModal()
            infodlg.Destroy()
            KeywordUsageReport.KeywordUsageReport(seriesName = series_name, episodeName = episode_name)

        else:
            raise MenuIDError

    def OnSearchTranscriptCommand(self, evt):
        """ Handle menuy selections for Search Transcript menu """
        n = evt.GetId() - self.cmd_id_start["searchtranscript"]
        sel = self.GetSelection()
        
        if n == 0:      # Open
            self.OnItemActivated(evt)                            # Use the code for double-clicking the Transcript

        elif n == 1:    # Drop for Search Results
            self.DropSearchResult(sel)

        else:
            raise MenuIDError

    def OnSearchCollectionCommand(self, evt):
        """Handle menu selections for Search Collection objects."""
        n = evt.GetId() - self.cmd_id_start["searchcollection"]
        sel = self.GetSelection()

        if n == 0:      # Cut
            self.cutCopyInfo['action'] = 'Move'    # Functionally, "Cut" is the same as Drag/Drop Move
            self.cutCopyInfo['sourceItem'] = sel
            self.OnCutCopyBeginDrag(evt)

        elif n == 1:    # Copy
            self.cutCopyInfo['action'] = 'Copy'
            self.cutCopyInfo['sourceItem'] = sel
            self.OnCutCopyBeginDrag(evt)

        elif n == 2:    # Paste
            # Open the Clipboard
            # wx.TheClipboard.Open()
            # specify the data formats to accept
            df = wx.CustomDataFormat('DataTreeDragData')
            # Specify the data object to accept data for this format
            cdo = wx.CustomDataObject(df)
            # Try to get the appropriate data from the Clipboard      
            success = wx.TheClipboard.GetData(cdo)
            # If we got appropriate data ...
            if success:
                # ... unPickle the data so it's in a usable format
                data = cPickle.loads(cdo.GetData())
                DragAndDropObjects.ProcessPasteDrop(self, data, sel, self.cutCopyInfo['action'])

        elif n == 3:      # Collection Summary Report
            CollectionSummaryReport.CollectionSummaryReport(self, sel)  # (self.GetPyData(sel), self.GetItemText(sel))

        elif n == 4:    # Drop for Search Results
            self.DropSearchResult(sel)

        elif n == 5:    # Keyword Usage Report
            # Specify the Keyword Usage Report, passing the selected item as the Search Collection
            # and passing in a pointer to the Tree Control.
            KeywordUsageReport.KeywordUsageReport(searchColl=sel, treeCtrl=self)

        elif n == 6:    # Play All Clips
            # Play All Clips takes the current Collection and the ControlObject as parameters.
            # (The ControlObject is owned not by the _DBTreeCtrl but by its parent)
            PlayAllClips.PlayAllClips(searchColl=sel, controlObject=self.parent.ControlObject, treeCtrl=self)

        elif n == 7:    # Rename
            self.EditLabel(sel)
            
        else:
            raise MenuIDError

    def OnSearchClipCommand(self, evt):
        """Handle selections for the Search Clip menu."""
        n = evt.GetId() - self.cmd_id_start["searchclip"]
        sel = self.GetSelection()
        selData = self.GetPyData(sel)
        clip_name = self.GetItemText(sel)
        coll_name = self.GetItemText(self.GetItemParent(sel))
        coll_parent_num = self.GetPyData(self.GetItemParent(sel)).parent
        
        if n == 0:      # Cut
            self.cutCopyInfo['action'] = 'Move'    # Functionally, "Cut" is the same as Drag/Drop Move
            self.cutCopyInfo['sourceItem'] = sel
            self.OnCutCopyBeginDrag(evt)

        elif n == 1:    # Copy
            self.cutCopyInfo['action'] = 'Copy'
            self.cutCopyInfo['sourceItem'] = sel
            self.OnCutCopyBeginDrag(evt)

        elif n == 2:    # Paste
            # Open the Clipboard
            # wx.TheClipboard.Open()
            # specify the data formats to accept
            df = wx.CustomDataFormat('DataTreeDragData')
            # Specify the data object to accept data for this format
            cdo = wx.CustomDataObject(df)
            # Try to get the appropriate data from the Clipboard      
            success = wx.TheClipboard.GetData(cdo)
            # If we got appropriate data ...
            if success:
                # ... unPickle the data so it's in a usable format
                data = cPickle.loads(cdo.GetData())
                DragAndDropObjects.ProcessPasteDrop(self, data, sel, self.cutCopyInfo['action'])

        elif n == 3:      # Open
            self.OnItemActivated(evt)                            # Use the code for double-clicking the Clip

        elif n == 4:    # Drop for Search Results
            self.DropSearchResult(sel)
            
        elif n == 5:    # Locate Clip in Episode
            # Load the Clip
            clip = Clip.Clip(selData.recNum)

            try:
                episode = Episode.Episode(clip.episode_num)

                if clip.transcript_num != 0:
                    transcript = Transcript.Transcript(clip.transcript_num)
                else:
                    transcriptList = DBInterface.list_transcripts(episode.series_id, episode.id)
                    if len(transcriptList) == 1:
                        transcript = Transcript.Transcript(transcriptList[0][0])
                    else:
                        strList = []
                        for (transcriptNum, transcriptID, episodeNum) in transcriptList:
                            strList.append(transcriptID)
                        dlg = wx.SingleChoiceDialog(self, _('Transana cannot identify the Transcript where this clip originated.\nPlease select the Transcript that was used to create this Clip.'), _('Transana Information'), strList, wx.OK | wx.CANCEL)
                        if dlg.ShowModal() == wx.ID_OK:
                            transcript = Transcript.Transcript(dlg.GetStringSelection(), episode.number)
                        else:
                            raise RecordNotFoundError (_('Transcript'), 0)

                if self.parent.ControlObject != None:
                    self.parent.ControlObject.LoadTranscript(episode.series_id, episode.id, transcript.id)
                    self.parent.ControlObject.SetVideoSelection(clip.clip_start, clip.clip_stop)

            except:
                (type, value, traceback) = sys.exc_info()
                # print "DatabaseTreeTab.OnClipCommand:  Exception raised.\nType = %s\nValue = %s\nTraceback = %s" % (type, value, traceback)
                dlg = Dialogs.ErrorDialog(self, _('The Transcript this Clip was created from cannot be loaded.\nMost likely, the transcript has been deleted.'))
                result = dlg.ShowModal()
                dlg.Destroy()

        elif n == 6:    # Rename
            self.EditLabel(sel)
            
        else:
            raise MenuIDError

    def DropSearchResult(self, selection):
        # Get the full Node Branch by climbing it to one level above the root
        nodeList = (self.GetItemText(selection),)
        originalNodeType = self.GetPyData(selection).nodetype
        while (self.GetItemParent(selection) != self.GetRootItem()):
            selection = self.GetItemParent(selection)
            nodeList = (self.GetItemText(selection),) + nodeList
            # print nodeList
        # Call the DB Tree's delete_Node method.
        self.delete_Node(nodeList, originalNodeType)
        
        

    def OnRightDown(self, event):
        """Called when the right mouse button is pressed."""
        # "Cut and Paste" functioning within the DBTree requires that we know information about how the user
        # is interacting with the data tree so that the Paste function can be enabled or disabled.
        # First, let's collect that information to be used later.
        
        # On the Mac, we need to explicitly select the Tree Node that's right-clicked on.
        if "__WXMAC__" in wx.PlatformInfo:
            # Items in the tree are not automatically selected with a right click.
            # We must select the item that is initially clicked manually!!
            # We do this by looking at the screen point clicked and applying the tree's
            # HitTest method to determine the current item, then actually selecting the item

            # This line works on Windows, but not on Mac or Linux using wxPython 2.4.1.2  due to a problem with event.GetPoint().
            # pt = event.GetPoint()
            # therfore, this alternate method is used.
            # Get the Mouse Position on the Screen in a more generic way to avoid the problem above
            (windowx, windowy) = wx.GetMousePosition()
            # Translate the Mouse's Screen Position to the Mouse's Control Position
            pt = self.ScreenToClientXY(windowx, windowy)
            # use HitTest to determine the tree item as the screen point indicated.
            sel_item, flags = self.HitTest(pt)
            # Select the appropriate item in the TreeCtrl
            self.SelectItem(sel_item)
        else:
            # Let's note what element in the tree was clicked.
            sel_item = self.GetSelection()
            
        # If you click off the tree in the Data Tab, you get an ugly wxPython Assertion Error.  Let's trap that.
        try:
            # Get the Node data associated with the selected item
            sel_item_data = self.GetPyData(sel_item)
            # For Paste to work, we need to remember what item was selected here.  This is because we will have lost
            # what item was selected in the DBTree by the time the user selects "Paste" from the popup menu otherwise.
            self.cutCopyInfo['destItem'] = sel_item

            # We look at the Clipboard here and determine if it has a Transana Data object in it.
            # Then we can poll the item type to determine if the Paste should be enabled.

            # Open the clipboard
            # wx.TheClipboard.Open()

            # specify the data formats to accept.
            #   Our data could be a DataTreeDragData object if the source is the Database Tree
            dfNode = wx.CustomDataFormat('DataTreeDragData')
            #   Our data could be a ClipDragDropData object if the source is the Transcript (clip creation)
            dfClip = wx.CustomDataFormat('ClipDragDropData')

            # Specify the data object to accept data for these formats
            #   A DataTreeDragData object will populate the cdoNode object
            cdoNode = wx.CustomDataObject(dfNode)
            #   A ClipDragDropData object will populate the cdoClip object
            cdoClip = wx.CustomDataObject(dfClip)

            # Create a composite Data Object from the object types defined above
            cdo = wx.DataObjectComposite()
            cdo.Add(cdoNode)
            cdo.Add(cdoClip)

            # Try to get data from the Clipboard
            success = wx.TheClipboard.GetData(cdo)

            # Close the Clipboard
            # wx.TheClipboard.Close()

            # If the data in the clipboard is in an appropriate format ...
            if success:
                # ... unPickle the data so it's in a usable form
                # First, let's try to get the DataTreeDragData object
                try:
                    source_item_data = cPickle.loads(cdoNode.GetData())
                except:
                    source_item_data = None
                    # If this fails, that's okay
                    pass

                # Let's also try to get the ClipDragDropData Object 
                try:
                    source_item_data2 = cPickle.loads(cdoClip.GetData())
                except:
                    source_item_data2 = None
                    # If this fails, that's okay
                    pass

                # if we didn't get a DataTreeDragData object, substitute the ClipDragDropData object
                if source_item_data == None:
                    source_item_data = source_item_data2

            # If the data in the clipboard is not appropriate ...
            else:
                # ... initialize data to an empty DataTreeDragDropData Object so that comparison operations will work
                source_item_data = DragAndDropObjects.DataTreeDragDropData()
                
            # This logic determines which context menu to pop-up based on what
            # type of item is selected
            if sel_item_data.nodetype == 'SeriesRootNode':
                menu = self.menu["series_root"]
            elif sel_item_data.nodetype == 'SeriesNode':
                menu = self.menu["series"]
                # Determine if the Paste menu item should be enabled 
                if DragAndDropObjects.DragDropEvaluation(source_item_data, sel_item_data):
                    menu.Enable(menu.FindItem(_('Paste')), True)
                else:
                    menu.Enable(menu.FindItem(_('Paste')), False)
            elif  sel_item_data.nodetype == 'EpisodeNode':
                menu = self.menu["episode"]
                # Determine if the Paste menu item should be enabled 
                if DragAndDropObjects.DragDropEvaluation(source_item_data, sel_item_data):
                    menu.Enable(menu.FindItem(_('Paste')), True)
                else:
                    menu.Enable(menu.FindItem(_('Paste')), False)
            elif sel_item_data.nodetype == 'TranscriptNode':
                menu = self.menu["transcript"]
            elif sel_item_data.nodetype == 'CollectionsRootNode':
                menu = self.menu["coll_root"]
            elif sel_item_data.nodetype == 'CollectionNode':
                menu = self.menu["collection"]
                # Determine if the Paste menu item should be enabled 
                if DragAndDropObjects.DragDropEvaluation(source_item_data, sel_item_data):
                    menu.Enable(menu.FindItem(_('Paste')), True)
                else:
                    menu.Enable(menu.FindItem(_('Paste')), False)
            elif sel_item_data.nodetype == 'ClipNode':
                menu = self.menu["clip"]
                # Determine if the Paste menu item should be enabled 
                if DragAndDropObjects.DragDropEvaluation(source_item_data, sel_item_data):
                    menu.Enable(menu.FindItem(_('Paste')), True)
                else:
                    menu.Enable(menu.FindItem(_('Paste')), False)
            elif sel_item_data.nodetype == 'KeywordRootNode':
                menu = self.menu["kw_root"]
            elif sel_item_data.nodetype == 'KeywordGroupNode':
                menu = self.menu["kw_group"]
                # Determine if the Paste menu item should be enabled 
                if DragAndDropObjects.DragDropEvaluation(source_item_data, sel_item_data):
                    menu.Enable(menu.FindItem(_('Paste')), True)
                else:
                    menu.Enable(menu.FindItem(_('Paste')), False)
            elif sel_item_data.nodetype == 'KeywordNode':
                menu = self.menu["kw"]
                # Determine if the Paste menu item should be enabled 
                if DragAndDropObjects.DragDropEvaluation(source_item_data, sel_item_data):
                    menu.Enable(menu.FindItem(_('Paste')), True)
                else:
                    menu.Enable(menu.FindItem(_('Paste')), False)
            elif sel_item_data.nodetype == 'KeywordExampleNode':
                menu = self.menu["kw_example"]
            elif sel_item_data.nodetype == 'NoteNode':
                menu = self.menu["note"]
            elif sel_item_data.nodetype == 'SearchRootNode':
                menu = self.menu["search"]
                # If Search Results exist ...
                if self.ItemHasChildren(sel_item):
                    # ... enable the "Clear All" menu item
                    menu.Enable(menu.FindItem(_('Clear All')), True)
                # If no Search Resutls exist ...
                else:
                    # ... disable the "Clear All" menu item.  (I could not figure out how to hide it.)
                    menu.Enable(menu.FindItem(_('Clear All')), False)
            elif sel_item_data.nodetype == 'SearchResultsNode':
                menu = self.menu["searchresults"]
            elif sel_item_data.nodetype == 'SearchSeriesNode':
                menu = self.menu["searchseries"]
            elif sel_item_data.nodetype == 'SearchEpisodeNode':
                menu = self.menu["searchepisode"]
            elif sel_item_data.nodetype == 'SearchTranscriptNode':
                menu = self.menu["searchtranscript"]
            elif sel_item_data.nodetype == 'SearchCollectionNode':
                menu = self.menu["searchcollection"]
            elif sel_item_data.nodetype == 'SearchClipNode':
                menu = self.menu["searchclip"]
            else:
                menu = self.gen_menu

            self.PopupMenu(menu, event.GetPosition())
        except:
            pass

    def OnItemActivated(self, event):
        """ Handles the double-click selection of items in the Database Tree """
        sel_item = self.GetSelection()                   # Identify the selected item
        sel_item_data = self.GetPyData(sel_item)         # Get the data associated with the selected item

        # print "Item Activated = %s, data = %s" % (self.GetItemText(sel_item), sel_item_data)

        if self.parent.ControlObject != None:                                                  # The ControlObject must be registered for anything to work

            # If the item is the Series Root, Add a Series
            if sel_item_data.nodetype == 'SeriesRootNode':
                # Change the eventID to match "Add Series"
                event.SetId(self.cmd_id_start["series_root"])
                # Call the Series Root Event Processor
                self.OnSeriesRootCommand(event)

            # If the item is a Series, Add an Episode
            elif sel_item_data.nodetype == 'SeriesNode':
                # Change the eventID to match "Add Episode"
                event.SetId(self.cmd_id_start["series"] + 1)
                # Call the Series Event Processor
                self.OnSeriesCommand(event)
                
            # If the item is an Episode, Add a Transcript
            elif sel_item_data.nodetype == 'EpisodeNode':
                # Change the eventID to match "Add Transcript"
                event.SetId(self.cmd_id_start["episode"] + 1)
                # Call the Episode Event Processor
                self.OnEpisodeCommand(event)
                
            # If the item is a Transcript, load the appropriate objects
            elif (sel_item_data.nodetype == 'TranscriptNode') or (sel_item_data.nodetype == 'SearchTranscriptNode'):
                seriesname=self.GetItemText(self.GetItemParent(self.GetItemParent(sel_item)))      # Capture the Series Name
                episodename=self.GetItemText(self.GetItemParent(sel_item))                         # Capture the Episode Name
                transcriptname=self.GetItemText(sel_item)                                          # Capture the Transcript Name
                self.parent.ControlObject.LoadTranscript(seriesname, episodename, transcriptname)  # Load everything via the ControlObject

            # If the item is the Collection Root, Add a Collection
            elif sel_item_data.nodetype == 'CollectionsRootNode':
                # Change the eventID to match "Add Collection"
                event.SetId(self.cmd_id_start["coll_root"])
                # Call the Collection Root Event Processor
                self.OnCollRootCommand(event)

            # If the item is a Collection, Add a Clip
            elif sel_item_data.nodetype == 'CollectionNode':
                # Change the eventID to match "Add Clip"
                event.SetId(self.cmd_id_start["collection"] + 3)
                # Call the Collection Event Processor
                self.OnCollectionCommand(event)

            # If the item is a Clip, capture the Clip Name and the nested list of Collections,
            # and then load the appropriate objects.  This includes Keyword Examples
            elif (sel_item_data.nodetype == 'ClipNode') or (sel_item_data.nodetype == 'SearchClipNode'):
                self.parent.ControlObject.LoadClipByNumber(sel_item_data.recNum)  # Load everything via the ControlObject

            # If the item is the Keyword Root, Add a Keyword Group
            elif sel_item_data.nodetype == 'KeywordRootNode':
                # Change the eventID to match "Add Keyword Group"
                event.SetId(self.cmd_id_start["kw_root"])
                # Call the Keyword Root Event Processor
                self.OnKwRootCommand(event)

            # If the item is a Keyword Group, Add a Keyword
            elif sel_item_data.nodetype == 'KeywordGroupNode':
                # Change the eventID to match "Add Keyword"
                event.SetId(self.cmd_id_start["kw_group"] + 1)
                # Call the Keyword Group Event Processor
                self.OnKwGroupCommand(event)

            # If the item is a Keyword, Display its properties (?)
            elif sel_item_data.nodetype == 'KeywordNode':
                # Change the eventID to match "Properties"
                event.SetId(self.cmd_id_start["kw"] + 4)
                # Call the Keyword Event Processor
                self.OnKwCommand(event)

            elif sel_item_data.nodetype == 'KeywordExampleNode':
                # Load the Clip
                sel_item_data = self.GetPyData(sel_item)                 # Get the Collection's data so we can test its nodetype
                self.parent.ControlObject.LoadClipByNumber(sel_item_data.recNum)  # Load everything via the ControlObject

            elif sel_item_data.nodetype == 'NoteNode':
                # We store the record number in the data for the node item
                num = self.GetPyData(sel_item).recNum
                n = Note.Note(num)
                n.lock_record()
                noteedit = NoteEditor.NoteEditor(self, n.text)
                n.text = noteedit.get_text()
                n.db_save()
                n.unlock_record()

            elif sel_item_data.nodetype == 'SearchRootNode':
                # Process the Search Request
                search = ProcessSearch.ProcessSearch(self, self.searchCount)
                # Get the new searchCount Value (which may or may not be changed)
                self.searchCount = search.GetSearchCount()

            # TODO:  Delete this!!
#            else:
#                tempstr = "Double-click processing for Selected Item = '%s', %s, has not been implemented" % (self.GetItemText(sel_item), sel_item_data)
#                dlg = wx.MessageDialog(self, tempstr, "Data Window", wx.OK | wx.ICON_EXCLAMATION)
#                dlg.ShowModal()
#                dlg.Destroy()
                
        # Make sure the selected object is expanded!
        self.Collapse(sel_item)
        

    def OnBeginLabelEdit(self, event):
        """ Process a request to edit a Tree Node Label, by vetoing it if it is not a Node that can be edited. """
        # Identify the selected item
        sel_item = self.GetSelection()
        # Get the data associated with the selected item
        sel_item_data = self.GetPyData(sel_item)
        # If the selected item iss not a Search Result Node
        # or a type that is explicitly handled in OnEndLabelEdit() ...
        if not (sel_item_data.nodetype in ['SeriesNode', 'EpisodeNode', 'TranscriptNode',
                                           'CollectionNode', 'ClipNode', 'NoteNode',
                                           'KeywordNode',
                                           'SearchResultsNode', 
                                           'SearchCollectionNode', 'SearchClipNode']):
            # ... then veto the edit process before it begins.
            event.Veto()

    def OnEndLabelEdit(self, event):
        """ Process the completion of editing a Tree Node Label by altering the underlying Data Object. """
        # Identify the selected item
        sel_item = self.GetSelection()
        # Get the data associated with the selected item
        sel_item_data = self.GetPyData(sel_item)
        try:
            # If ESC is pressed ...
            if event.IsEditCancelled():
                # ... don't edit the label or do any processing.
                event.Veto()
            # Otherwise ...
            else:
                
                # If we are renaming a Series Record...
                if sel_item_data.nodetype == 'SeriesNode':
                    # Load the Series
                    tempObject = Series.Series(sel_item_data.recNum)
                    # TODO:  MU Messaging needed here!

                # If we are renaming an Episode Record...
                elif sel_item_data.nodetype == 'EpisodeNode':
                    # Load the Episode
                    tempObject = Episode.Episode(sel_item_data.recNum)
                    
                # If we are renaming a Transcript Record...
                elif sel_item_data.nodetype == 'TranscriptNode':
                    # Load the Transcript
                    tempObject = Transcript.Transcript(sel_item_data.recNum)
                    
                # If we are renaming a Collection Record...
                elif sel_item_data.nodetype == 'CollectionNode':
                    # Load the Collection
                    tempObject = Collection.Collection(sel_item_data.recNum)

                # If we are renaming a Clip Record...
                elif sel_item_data.nodetype == 'ClipNode':
                    # Load the Clip
                    tempObject = Clip.Clip(sel_item_data.recNum)

                # If we are renaming a Note Record...
                elif sel_item_data.nodetype == 'NoteNode':
                    # Load the Note
                    tempObject = Note.Note(sel_item_data.recNum)

                # If we are renaming a Keyword Record...
                elif sel_item_data.nodetype == 'KeywordNode':
                    # Load the Keyword
                    tempObject = Keyword.Keyword(sel_item_data.parent, self.GetItemText(sel_item))

                # If we are renaming a SearchCollection or a SearchClip ...
                elif sel_item_data.nodetype == 'SearchResultsNode' or \
                     sel_item_data.nodetype == 'SearchCollectionNode' or \
                     sel_item_data.nodetype == 'SearchClipNode':
                    # ... we don't actually need to do anything, as there is no underlying object that
                    # needs changing.  But we don't veto the Rename either.
                    tempObject = None

                # If we haven't defined how to process the label change, veto it.
                else:
                    # Indicate that no Object has been loaded, so no object will be processed.
                    tempObject = None
                    # Veto the event to cancel the Renaming in the Tree
                    event.Veto()

                # If an object was successfully loaded ...
                if tempObject != None:
                    # We can't just rename a Transcript if it is currently open.  Saving the Transcript that's been
                    # renamed would wipe out the change, and causing problems with data integrity.  Let's test for that
                    # condition and block the rename.
                    if (sel_item_data.nodetype == 'TranscriptNode') and \
                       (self.parent.ControlObject.TranscriptNum == tempObject.number):
                        dlg = Dialogs.ErrorDialog(self.parent, _('You cannot rename the Transcript that is currently loaded.\nSelect "File" > "New" and try again.'))
                        dlg.ShowModal()
                        dlg.Destroy()
                        event.Veto()
                    else:
                        # Lock the Object
                        tempObject.lock_record()
                        # If we are renaming a keyword ...
                        if sel_item_data.nodetype == 'KeywordNode':
                            # ... Change the Object's Keyword property
                            tempObject.keyword = event.GetLabel()
                        # If we're not renaming a keyword ...
                        else:
                            # ... Change the Object Name
                            tempObject.id = event.GetLabel()
                            
                        # Save the Object
                        tempObject.db_save()
                        # Unlock the Object
                        tempObject .unlock_record()
                        # TODO:  MU Messaging needed here!
                        
            self.Refresh()

        except:
            event.Veto()
            dlg = Dialogs.ErrorDialog(self.parent, _("Object Rename failed.  The Object is probably locked by another user."))
            dlg.ShowModal()
            dlg.Destroy()
            

    def KeywordMapReport(self, seriesName, episodeName):
        """ Produce a Keyword Map Report for the specified Series & Episode """
        frame = KeywordMapClass.KeywordMap(None, -1, _("Transana Keyword Map Report"))
        frame.Setup(seriesName = seriesName, episodeName = episodeName)

    def ConvertSearchToCollection(self, sel, selData):
        """ Converts all the Collections and Clips in a Search Result node to a Collection. """
        # This method takes a tree node and iterates through it's children, coverting them appropriately.
        # If one of those children HAS children of its own, this method should be called recursively.
        
        # print "Converting ", self.GetItemText(sel), selData

        # Things can come up to interrupt our process, but assume for now that we should continue
        contin = True

        # If we have the Search Results Node, create a Collection to be the root of the Converted Search Result
        if selData.nodetype == 'SearchResultsNode':
            # Create a new Collection
            tempCollection = Collection.Collection()
            # Assign the Search Results Name to the Collection
            tempCollection.id = self.GetItemText(sel)
            # Load the Collection Properties Form
            contin = self.parent.edit_collection(tempCollection)
            # If the user said OK (did not cancel) ,,,
            if contin:
                # Add the new Collection for the Search Result to the DB Tree
                nodeData = (_('Collections'), tempCollection.id)
                self.add_Node('CollectionNode', nodeData, tempCollection.number, 0, True)
                # Now that this is a collection, let's update the Node Data to reflect the correct data
                selData.recNum = tempCollection.number
                selData.parent = tempCollection.parent
                # If the user changed the name for the Collection, we need to update the Search Results Node
                self.SetItemText(sel, tempCollection.id)


        if contin:
            # Initialize the Sort Order Counter
            sortOrder = 1
            (childNode, cookieItem) = self.GetFirstChild(sel)
            while 1:
                childData = self.GetPyData(childNode)
                if childData.nodetype == 'SearchSeriesNode':
                    # print "SearchSeries %s:  Drop this." % self.GetItemText(childNode)
                    pass
                elif childData.nodetype == 'SearchCollectionNode':
                    # print "SearchCollection %s: Convert to Collection." % self.GetItemText(childNode)
            
                    # Load the existing Collection
                    sourceCollection = Collection.Collection(childData.recNum)
                    # Duplicate this Collection
                    newCollection = sourceCollection.duplicate()
                    # The user may have changed the Node Text, indicating they want the new Collection to
                    # have a different Name
                    newCollection.id = self.GetItemText(childNode)
                    # The new Collection has a different parent than the old one!
                    newCollection.parent = selData.recNum
                    # Save the new Collection
                    newCollection.db_save()
                    # Now that this is a Collection, let's update the Node Data to reflect the correct data
                    childData.recNum = newCollection.number
                    childData.parent = newCollection.parent
                    # Add the new Collection for the Search Result to the DB Tree
                    nodeData = ()
                    tempNode = childNode
                    while 1:
                        nodeData = (self.GetItemText(tempNode),) + nodeData
                        tempNode = self.GetItemParent(tempNode)
                        if self.GetPyData(tempNode).nodetype == 'SearchRootNode':
                            break
                        
                    self.add_Node('CollectionNode', (_('Collections'),) + nodeData, newCollection.number, newCollection.parent, True)

                    if self.ItemHasChildren(childNode):
                        self.ConvertSearchToCollection(childNode, childData)

                elif childData.nodetype == 'SearchClipNode':

                    # print "SearchClip %s: Convert to Clip." % self.GetItemText(childNode)

                    # Load the existing Clip
                    sourceClip = Clip.Clip(childData.recNum)
                    # Duplicate this Clip
                    newClip = sourceClip.duplicate()
                    # The user may have changed the Node Text, indicating they want the new Clip to
                    # have a different Name
                    newClip.id = self.GetItemText(childNode)
                    # The new Clip has a different parent than the old one!
                    newClip.collection_num = selData.recNum
                    # Add in a Sort Order, which is not carried over during Clip Duplication
                    newClip.sort_order = sortOrder
                    # Increment the Sort Order Counter
                    sortOrder += 1
                    # Save the new Clip
                    newClip.db_save()
                    # Now that this is a Clip, let's update the Node Data to reflect the correct data
                    childData.recNum = newClip.number
                    childData.parent = newClip.collection_num
                    # Add the new Collection for the Search Result to the DB Tree
                    nodeData = ()
                    tempNode = childNode
                    while 1:
                        nodeData = (self.GetItemText(tempNode),) + nodeData
                        tempNode = self.GetItemParent(tempNode)
                        if self.GetPyData(tempNode).nodetype == 'SearchRootNode':
                            break

                    self.add_Node('ClipNode', (_('Collections'),) + nodeData, newClip.number, newClip.collection_num, True)

                else:
                    print "DatabaseTreeTab._DBTreeCtrl.ConvertSearchToCollection(): Unhandled Child Node:", self.GetItemText(childNode), childData
                if childNode != self.GetLastChild(sel):
                    (childNode, cookieItem) = self.GetNextChild(sel, cookieItem)
                else:
                    break
        # Return the "contin" value to indicate whether the conversion proceeded.
        return contin

    def GetObjectNodeType(self):
        # Get the Mouse Position on the Screen
        (windowx, windowy) = wx.GetMousePosition()
        # Translate the Mouse's Screen Position to the Mouse's Control Position
        (x, y) = self.ScreenToClientXY(windowx, windowy)
        # Now use the tree's HitTest method to find out about the potential drop target for the current mouse position
        (id, flag) = self.HitTest((x, y))

        # Add Exception handling here to handle "off-tree" exception
        try:
            # I'm using GetItemText() here, but could just as easily use GetPyData()
            if self.GetPyData(id) != None:
                destData = self.GetPyData(id).nodetype
            else:
                destData = 'None'
            return destData
        except:
            return 'None'

""" Something """

from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from inbox.models.message import SpoolMessage
from inbox.models.thread import DraftThread


from inbox.log import get_logger
log = get_logger()


def get_or_copy_draft(session, draft_public_id):
    try:
        draft = session.query(SpoolMessage).filter(
            SpoolMessage.public_id == draft_public_id).one()
    except NoResultFound:
        log.info('NoResultFound for draft with public_id {0}'.
                 format(draft_public_id))
        raise
    except MultipleResultsFound:
        log.info('MultipleResultsFound for draft with public_id {0}'.
                 format(draft_public_id))
        raise

    # For non-conflict draft updates i.e. the draft that has not
    # already been updated, simply return the draft. This is set as the
    # parent of the new draft we create (updating really creates a new
    # draft because drafts are immutable)
    if not draft.child_draft:
        return draft

    # For conflict draft updates i.e. the draft has already been updated,
    # return a copy of the draft, which is set as the parent of the new
    # draft created.
    assert not draft.draft_copied_from, 'Copy of a copy!'

    # We *must not* copy the following attributes:
    # 'id', 'public_id', 'child_draft', 'draft_copied_from',
    # 'replyto_thread_id', 'replyto_thread', '_sa_instance_state',
    # 'inbox_uid'
    copy_attrs = ['decode_error', 'resolved_message_id',
                  'updated_at', 'sender_addr', 'thread_id',
                  'bcc_addr', 'cc_addr', 'references', 'discriminator',
                  'deleted_at', 'sanitized_body', 'subject', 'g_msgid',
                  'from_addr', 'g_thrid', 'snippet', 'is_sent',
                  'message_id_header', 'received_date', 'size', 'to_addr',
                  'mailing_list_headers', 'is_read', 'parent_draft_id',
                  'in_reply_to', 'is_draft', 'created_at', 'data_sha256',
                  'created_date', 'reply_to']

    draft_copy = SpoolMessage()
    for attr in draft.__dict__:
        if attr in copy_attrs:
            setattr(draft_copy, attr, getattr(draft, attr))

    draft_copy.thread = draft.thread
    draft_copy.resolved_message = draft.resolved_message
    draft_copy.parts = draft.parts
    draft_copy.contacts = draft.contacts

    draft_copy.parent_draft = draft.parent_draft

    draft_copy.draft_copied_from = draft.id

    if draft.replyto_thread:
        draft_copy.replyto_thread = DraftThread.create_copy(
            draft.replyto_thread)

    return draft_copy

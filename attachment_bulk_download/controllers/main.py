# -*- coding: utf-8 -*-
# Part of attachment_bulk_download. License: LGPL-3 <https://www.gnu.org/licenses/lgpl-3.0.html>.
import logging

from werkzeug.exceptions import BadRequest, NotFound

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import content_disposition, request

_logger = logging.getLogger(__name__)

WIZARD_MODEL = 'attachment.bulk.download.wizard'


class AttachmentBulkDownloadController(http.Controller):

    @http.route('/attachment_bulk_download/<int:wizard_id>', type='http',
                auth='user', methods=['GET'])
    def attachment_bulk_download(self, wizard_id, **kwargs):
        """Serve the ZIP of a download request the current user prepared.

        Only the wizard id travels through the browser. The attachments are
        resolved again here, in the name of the logged-in user and through
        ir.attachment.search(), so ids coming from the client can never widen
        what ends up in the archive. A wizard prepared by somebody else is
        answered with 404, exactly like an unknown id.
        """
        try:
            wizard = request.env[WIZARD_MODEL].browse(wizard_id).exists()
            if not wizard:
                raise NotFound()
            # same 404 for "unknown id" and "not yours": no enumeration oracle
            wizard._abd_assert_owner()
            filename, content = wizard._abd_build_zip()
        except AccessError:
            _logger.info('Bulk download %s refused for user %s',
                         wizard_id, request.env.uid)
            raise NotFound()
        except UserError as error:
            # the message is rendered into an HTML error page: log the detail
            # and answer with a fixed description
            _logger.info('Bulk download %s refused: %s', wizard_id, error)
            raise BadRequest(
                'This download was refused. Reopen the Download Attachments '
                'dialog to see why.')
        return request.make_response(content, headers=[
            ('Content-Type', 'application/zip'),
            ('Content-Length', str(len(content))),
            ('Content-Disposition', content_disposition(filename)),
        ])

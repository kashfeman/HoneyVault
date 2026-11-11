"""Startup checks without starting or stopping the user's preview."""

import socket
import unittest
from unittest.mock import patch

from scripts.preview_frontend import check_preview_port, create_preview_app, main


class StartupTests(unittest.TestCase):
    def test_occupied_port_exits_with_restart_instructions(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            with self.assertRaisesRegex(SystemExit, "Stop the existing preview"):
                check_preview_port("127.0.0.1", listener.getsockname()[1])

    def test_main_serves_the_same_factory_instance_with_admin_routes(self):
        app = create_preview_app()
        with patch("scripts.preview_frontend.check_preview_port"), \
                patch("scripts.preview_frontend.create_preview_app", return_value=app), \
                patch.object(app, "run") as run, patch("builtins.print"):
            main()
        run.assert_called_once_with(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
        client = app.test_client()
        for path in ("/dashboard/manage-documents", "/dashboard/alerts", "/dashboard/events"):
            self.assertEqual(client.get(path).status_code, 200)

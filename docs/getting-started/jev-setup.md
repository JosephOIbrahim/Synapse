# Set up JEV assistance

Open **Connect models → JEV / TypeSafe key setup**.

Paste your TypeSafe API key into the masked **TypeSafe API key** field, then choose **Save session key**. The key remains in memory until Houdini closes. Closing the setup dialog or refreshing the panel keeps a saved session key; unsaved text is discarded when you close the dialog.

Saving a key does not enable JEV or verify that the service accepts it. The key status says **Validity has not been checked**.

To use assistance, choose **Rank selected-network actions** or **Measure routing**, then **Save JEV preferences**. Review **JEV permissions…** to allow TypeSafe for the current project. Your generation model stays selected.

**Clear session key** removes the key saved through this dialog. If `TYPESAFE_API_KEY` is already configured in the environment or Windows user environment, SYNAPSE falls back to it and shows that in the status. The session field does not overwrite or delete that configuration.

The key is never written into panel settings. Authentication uses TypeSafe's [documented API](https://docs.typesafe.ai/api). The implementation is in `python/synapse/jev/credentials.py` and `python/synapse/panel/connection_dialog.py`; the existing adapter still enforces request permissions.

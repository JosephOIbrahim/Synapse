# Windows installer filming walkthrough

This is a filming plan, not a claim that the live GUI/model checks have been
recorded. Use a disposable Windows/Houdini test profile. The published installer
preview is unsigned.

| Shot | On-screen action | Suggested narration |
| --- | --- | --- |
| 1. Start | Show the downloaded `SYNAPSE-5.67.4-Setup.exe`, then open it after saving and closing Houdini. | "One Setup wizard installs SYNAPSE and its Houdini interface." |
| 2. Choose Houdini | Show the detected build and actual Python version. Select Houdini 22.0.400 / Python 3.13. | "Choose the Houdini build you use." |
| 3. Confirm preferences | Show the suggested preference folder. Demonstrate browsing only if the test profile uses OneDrive or a custom folder. | "Confirm the same preference folder your Houdini launcher uses." |
| 4. Review and install | Show the dedicated application directory and ready page, then click Install. Keep the migration option unchecked on a fresh profile. | "Setup installs the runtime, registers its panel and shelf, and verifies the files." |
| 5. Show completion | Capture the actual successful file/registration result. | "The files passed verification. Next we check the running Houdini session." |
| 6. Open SYNAPSE | Launch the selected Houdini test profile, open New Pane Tab → Synapse, enable its shelf, and run Doctor. | "Open SYNAPSE and read the live component checks." |
| 7. Connect a model | Open Connect models. Choose a configured provider/model, Check connection, then Use this model. Keep credentials out of the recording. | "Model access is a separate step. Choose your service and verify its connection." |
| 8. First interaction | In a disposable scene, ask for a box, inspect the nodes and demonstrate the actual result. | "Describe a small task, inspect what changed, and keep control of the scene." |

Do not film a PASS substitute for an absent component. Doctor's Moneta schema-use
row remained unresolved in the headless installer probe; record the real result
in the filming profile. If model access is unavailable, stop at the connection
screen and label it unverified. The installer does not ship a model or a key.

For a short maintenance insert, close Houdini, run a newer reviewed Setup and
show the retained preferences. Then use Windows Installed apps → SYNAPSE →
Uninstall in the disposable profile. Explain that artist data is retained and
that uninstall restores a backed-up source registration when migration was used.

Native wizard visual inspection and this full live walkthrough were not completed
in the builder session: the computer-use app approval timed out. The compiled
silent lifecycle and separate offscreen Houdini probe have their own evidence in
the [verification record](windows-installer-verification.md).

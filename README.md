Python script that presses certain controller buttons on certain keyboard inputs, to mimic the controls of The Binding of Isaac.
This can be used to allow using a keyboard to play multiplayer via Steam Remote Play.

Works on Linux in X11 and Wayland. Must be run as Root.

Required dependencies can be found in `pyproject.toml`. Run using `python3 main.py`, then select the input device to listen to (your keyboard).

The keyboard's inputs do not get overridden. Because most apps ignore controller input and Steam Remote play ignores keyboard input (make sure to have keyboard access turned off), this means that the keyboard can still be used normally while the script is running.

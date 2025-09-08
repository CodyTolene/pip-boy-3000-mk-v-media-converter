<div align="center">
  <img align="center" src=".github/images/tool.png" />
  <h1 align="center">Pip-Boy 3000 Mk V - Media Conversion Tool</h1>
  <p align="center">
    A simple tool for batch converting music and video files for use on the
    <a href="https://www.thewandcompany.com/fallout-pip-boy/">Pip-Boy 3000 Mk V</a>
    crafted by <a href="https://www.thewandcompany.com/">The Wand Company</a>!
  </p>
</div>

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

## Index <a name="index"></a>

- [Intro](#intro)
  - [Media Conversion Tool](#tool)
  - [Preview](#preview)
- [User Guide](#user-guide)
  - [Running (Windows)](#running-windows)
- [Development / Code Contribution](#local-development)
  - [Prerequisites](#prerequisites)
  - [Workspace Setup](#workspace-setup)
  - [Build / Run](#build-run)
- [License(s)](#licenses)
- [Wrapping Up](#wrapping-up)

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

## Intro

### **Media Conversion Tool** <a name="tool"></a>

The **Media Conversion Tool** is designed to simplify the process of preparing
video and music files for the Pip-Boy 3000 Mk V device. It offers a user-friendly
interface and powerful features:

- Converting an entire list of video or music files in sequence.
- Adjust the volume gain for music files easily to maximize playback volume.
- Adjust video scaling to match your needs (defaults to the screen resolution of
  480x320, full-screen).

<p align="right">[ <a href="#index">Index</a> ]</p>

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

#### Preview(s) <a name="preview"></a>

**"Music" Tab Preview:**

![Music Tab Screenshot][img-screenshot-01]

**"Video" Tab Preview:**

![Video Tab Screenshot][img-screenshot-02]

<p align="right">[ <a href="#index">Index</a> ]</p>

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

## User Guide <a name="user-guide"></a>

### Running (Windows) <a name="running-windows"></a>

Go to the [releases page][url-releases] and download the latest
`Pip-Boy-3000-Mk-V-Media-Converter.exe` file. Once downloaded, run the executable
to start the application.

<p align="right">[ <a href="#index">Index</a> ]</p>

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

## Development / Code Contribution <a name="local-development"></a>

You can contribute to the development of **Pip-Boy 3000 Mk V Media Conversion Tool** by
following these steps:

### Prerequisites <a name="prerequisites"></a>

1. Make sure you have `Python` installed and accessible in your `PATH`:

   [python.org/downloads](https://www.python.org/downloads/)

   Test with:

   ```bash
   python --version
   # or
   py --version
   ```

2. Make sure you have `ffmpeg` installed one of two ways:

   - Install locally and accessible in your `PATH`: [ffmpeg.org/download](https://www.ffmpeg.org/download.html) and/or

   - Binaries (optional): [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) (placed in `bin/`)

<p align="right">[ <a href="#index">Index</a> ]</p>

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

### Workspace Setup <a name="workspace-setup"></a>

1. Bootstrap `pip`:

   ```bash
   py -m ensurepip --upgrade
   py -m pip install --upgrade pip setuptools wheel
   ```

2. Install third party dependencies:

   ```base
   py -m pip install -r requirements.txt
   ```

3. If you don't want to install `ffmpeg` locally, place the `ffmpeg.exe` binary in the `bin/` folder. Test:

   ```bash
   cd bin
   ffmpeg -version
   ```

<p align="right">[ <a href="#index">Index</a> ]</p>

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

### Build / Run <a name="build-run"></a>

To run the application directly from root for development (requires local ffmpeg or from bin):

   ```bash
   py main.py
   ```

To build `dist/main.exe` for production (requires ffmpeg in bin):

   ```bash
   py -m PyInstaller --onefile ^
      --windowed ^
      --noconfirm ^
      --name Pip-Boy-3000-Mk-V-Media-Converter ^
      --icon=icon.ico ^
      --add-data "bin;bin" ^
      main.py
   ```

<p align="right">[ <a href="#index">Index</a> ]</p>

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

### Linting and Formatting

To ensure code quality and consistency, this project uses the following tools:

- **[Black](https://black.readthedocs.io/en/stable/)**: An opinionated code formatter for Python.
- **[Flake8](https://flake8.pycqa.org/en/latest/)**: A linting tool for Python that checks for style guide enforcement.

Run the following command to format your code with Black:

```bash
py -m black .
```

Run the following command to check your code with Flake8:

```bash
py -m flake8
```

## License(s) <a name="licenses"></a>

This project is licensed under the Creative Commons Attribution-NonCommercial
4.0 International License. See the [license][url-license] file for more
information.

This software uses FFmpeg licensed under the [LGPLv2.1][url-license-lgpl] license. Source code for FFmpeg is available at [https://ffmpeg.org](https://ffmpeg.org).

`SPDX-License-Identifiers: CC-BY-NC-4.0, LGPLv2.1`

> ![Info][img-info] The application code is licensed under `CC-BY-NC-4.0`. FFmpeg is licensed separately under `LGPLv2.1`. These licenses apply independently.

<p align="right">[ <a href="#index">Index</a> ]</p>

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

## Wrapping Up <a name="wrapping-up"></a>

Thank you to The Wand Company for the [Pip-Boy 3000 Mk V](https://www.thewandcompany.com/fallout-pip-boy/), a fantastic piece of hardware and one of my favorites!

**Note:** This tool is a rapid prototype built with assistance from an AI pair-programming tool to speed up development. The goals of this project are primarily:

- To create a useful tool for Pip-Boy 3000 Mk V users.
- To learn how to build quick Windows desktop applications with Python and Tkinter.
- To be able to create more ffmpeg-based wrapper tools in the future for other devices.
- To effectively put together linting and formatting tools for Python projects.
- To learn how to package and build standalone Windows executables with PyInstaller.

If you find this tool useful, please consider supporting my work. Your support helps me continue developing and maintaining this project. If you have any questions, suggestions, or issues, please feel free to reach out or open an issue on the [GitHub repository][url-new-issue].

| Type                                                                      | Info                                                           |
| :------------------------------------------------------------------------ | :------------------------------------------------------------- |
| <img width="48" src=".github/images/ng-icons/email.svg" />                | webmaster@codytolene.com                                       |
| <img width="48" src=".github/images/simple-icons/github.svg" />           | https://github.com/sponsors/CodyTolene                         |
| <img width="48" src=".github/images/simple-icons/buymeacoffee.svg" />     | https://www.buymeacoffee.com/codytolene                        |
| <img width="48" src=".github/images/simple-icons/bitcoin-btc-logo.svg" /> | bc1qfx3lvspkj0q077u3gnrnxqkqwyvcku2nml86wmudy7yf2u8edmqq0a5vnt |

Fin. Happy programming friend!

Cody Tolene

<p align="right">[ <a href="#index">Index</a> ]</p>

<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->
<!---------------------------------------------------------------------------->

<!-- IMAGE REFERENCES -->

[img-info]: .github/images/ng-icons/info.svg
[img-screenshot-01]: .github/images/screenshots/screen_01.png
[img-screenshot-02]: .github/images/screenshots/screen_02.png
[img-warn]: .github/images/ng-icons/warn.svg

<!-- LINK REFERENCES -->

[url-license-lgpl]: /LICENSE-LGPL.md
[url-license]: /LICENSE.md
[url-new-issue]: https://github.com/CodyTolene/pip-boy-3000-mk-v-media-converter/issues
[url-releases]: https://github.com/CodyTolene/pip-boy-3000-mk-v-media-converter/releases

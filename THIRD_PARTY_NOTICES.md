# Third-party notices and licensing scope

This is a preliminary dependency inventory, not a complete legal or supply-chain audit. No third-party component is relicensed by the project's AGPL-3.0-only grant.

| Component | Principal upstream license or terms |
| --- | --- |
| [Ultralytics 8.2.103](https://github.com/ultralytics/ultralytics/blob/v8.2.103/LICENSE) | AGPL-3.0; alternative Enterprise terms available from Ultralytics |
| [Flask](https://github.com/pallets/flask) | BSD-3-Clause |
| [Flask-CORS](https://github.com/corydolphin/flask-cors) | MIT |
| [OpenCV](https://github.com/opencv/opencv) | Apache-2.0; Python wheel packaging and bundled components have separate notices |
| [NumPy](https://github.com/numpy/numpy) | BSD-3-Clause |
| [Matplotlib](https://matplotlib.org/stable/project/license.html) | Matplotlib license based on PSF |
| [PyTorch](https://github.com/pytorch/pytorch) | BSD-3-Clause; bundled components may differ |
| [React](https://github.com/facebook/react) and Create React App scaffolding | MIT; preserve upstream notices and observe separate logo/trademark terms |
| Material UI, Emotion, Axios, Chart.js, Styled Components | MIT, subject to the respective upstream notices |
| [Olive Fruit Detection dataset](https://universe.roboflow.com/aliasghar/olive-fruit-detection/dataset/1) | Dataset page reports CC BY 4.0; see docs/MODEL_AND_DATA_LICENSING.md |

The pinned frontend lockfile contains 1,435 dependency entries at the time of this review. License metadata is not a substitute for inspecting original license files, dual-license choices and bundled binaries. In particular, exit, the nested esprima package and the nested prelude-ls package lack license metadata in the lockfile. The root and backend npm manifests also require review; the legacy backend package.json declares ISC, which is not the license of the current original project as a whole. Preserve any valid pre-existing grants and third-party notices. Do not treat this inventory as exhaustive.

Before distributing a bundled build, audit all resolved Python and npm dependencies, bundled binary libraries and template/assets, retain applicable notices, and establish the scope of Corresponding Source under AGPL-3.0.

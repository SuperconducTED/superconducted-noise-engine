# PR #44 verification · Burak's desktop · 2026-08-31

**Commit tested**: `7fc95bb45c21adacdac957882881c0c00fb4aea6`
**Branch**: `feature/mert-issue-35-consequent-degeneracy`
**Verdict**: VERIFIED
**ADR-024 clause 1**: RATIFY - The primitive module shouldn't be hard-coded with upper-layer defuzzifier knowledge (layering principle).

## Machine

| Field | Value |
| --- | --- |
| OS | Microsoft Windows 10 Home 10.0.19045 |
| CPU | AMD Ryzen 5 5500 |
| RAM | 15.9 GB |
| Python | Python 3.12.10 |
| Install | fresh clone, fresh venv, requirements.txt + requirements-dev.txt |

## Results

| Check | Expected (as written in the runbook) | Observed |
| --- | --- | --- |
| ruff check . | All checks passed! | All checks passed! |
| ruff format --check . | no file needs reformatting | 36 files already formatted |
| mypy --strict src/superconducted | no issues in 22 source files | Success: no issues found in 22 source files |
| pytest tests/ -q | 0 failed | 187 passed, 0 failed |
| collect-only vs NC-021 row | the two agree | 187 == 187 |
| NC-021 prose names a measurement commit | yes | yes (571ffbc) |
| pytest tests/test_channel_viability.py | 0 failed | 21 passed, 0 failed |
| [0,0] projects to identity | True, max diff 0.0 | True \| max\|diff\|: 0.0 |
| [0.2,0.1] projects to identity | False | False |
| degeneracy rate, endpoint vs interior | the two agree | 0.242 and 0.242 |
| rate test, 4 parametrizations | 0 failed | 4 passed, 0 failed |
| mutation applied \| rate test fails | 10 failed | 10 failed |
| after git checkout -- restore \| 0 failed | 0 failed | 0 failed |
| smoke run seeds, endpoint / interior | 1 / 0, same as PR #34 | 1 / 0 |
| n_rules | 27 | 27 |

## ADR-024 judgement

**Clause 1:** Ratify. The argument holds perfectly. A lower-level module like `from_grid` genuinely cannot and should not know the defuzzification or squashing strategy of the upper layers. Forcing it to guarantee viability by biasing it positively would hard-code assumptions that break under `SigmoidSquashing`. Nothing should change in `tsk.py`.

**Clause 2:** This is Bengisu's call regarding the `channels/` lock, but keeping `is_identity_damping` in `integration/aer_factory.py` makes sense until `ChannelProjector` grows a viability method. The behavior change for short vectors raising an error is also logical (a short vector isn't an identity channel).

## Notes

None.

## Full transcript

**********************
Windows PowerShell transcript start
Start time: 20260831012543
Username: DESKTOP-2CST637\PC
RunAs User: DESKTOP-2CST637\PC
Configuration Name: 
Machine: DESKTOP-2CST637 (Microsoft Windows NT 10.0.19045.0)
Host Application: C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe
Process ID: 20816
PSVersion: 5.1.19041.6456
PSEdition: Desktop
PSCompatibleVersions: 1.0, 2.0, 3.0, 4.0, 5.0, 5.1.19041.6456
BuildVersion: 10.0.19041.6456
CLRVersion: 4.0.30319.42000
WSManStackVersion: 3.0
PSRemotingProtocolVersion: 2.3
SerializationVersion: 1.1.0.1
**********************
Transcript started, output file is C:\scted-verify\pr44-transcript.txt
PS C:\scted-verify> git clone https://github.com/SuperconducTED/superconducted-noise-engine.git pr44
Set-Location C:\scted-verify\pr44
Cloning into 'pr44'...
remote: Enumerating objects: 8532, done.
remote: Counting objects: 100% (308/308), done.
remote: Compressing objects: 100% (194/194), done.
remote: Total 8532 (delta 173), reused 149 (delta 110), pack-reused 8224 (from 2)
Receiving objects: 100% (8532/8532), 44.46 MiB | 22.75 MiB/s, done.
Resolving deltas: 100% (5100/5100), done.
PS C:\scted-verify\pr44> git checkout feature/mert-issue-35-consequent-degeneracy
git rev-parse HEAD
branch 'feature/mert-issue-35-consequent-degeneracy' set up to track 'origin/feature/mert-issue-35-consequent-degeneracy
'.
Switched to a new branch 'feature/mert-issue-35-consequent-degeneracy'
7fc95bb45c21adacdac957882881c0c00fb4aea6
PS C:\scted-verify\pr44> git log --oneline -4
7fc95bb (HEAD -> feature/mert-issue-35-consequent-degeneracy, origin/feature/mert-issue-35-consequent-degeneracy) docs:
carry the desktop runbook into the implementation doc
5b36de0 docs: stamp NC-021 with the commit its 187 was measured at
571ffbc feat(integration): ship the channel-viability contract — ADR-024 (Closes #35)
9792017 (origin/main, origin/HEAD, main) Merge pull request #43 from SuperconducTED/chore/lf-renormalization
PS C:\scted-verify\pr44> python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1

PS C:\scted-verify\pr44>
(.venv) python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
pip install -e . --no-deps
Requirement already satisfied: pip in c:\scted-verify\pr44\.venv\lib\site-packages (25.0.1)
Collecting pip
  Using cached pip-26.2.1-py3-none-any.whl.metadata (4.6 kB)
Using cached pip-26.2.1-py3-none-any.whl (1.8 MB)
Installing collected packages: pip
  Attempting uninstall: pip
    Found existing installation: pip 25.0.1
    Uninstalling pip-25.0.1:
      Successfully uninstalled pip-25.0.1
Successfully installed pip-26.2.1
Collecting qiskit==2.4.1 (from -r requirements.txt (line 3))
  Using cached qiskit-2.4.1-cp310-abi3-win_amd64.whl.metadata (13 kB)
Collecting qiskit-aer==0.17.2 (from -r requirements.txt (line 4))
  Using cached qiskit_aer-0.17.2-cp312-cp312-win_amd64.whl.metadata (8.5 kB)
Collecting qiskit-ibm-runtime==0.46.1 (from -r requirements.txt (line 5))
  Using cached qiskit_ibm_runtime-0.46.1-py3-none-any.whl.metadata (21 kB)
Collecting numpy==2.4.4 (from -r requirements.txt (line 7))
  Using cached numpy-2.4.4-cp312-cp312-win_amd64.whl.metadata (6.6 kB)
Collecting scipy==1.17.1 (from -r requirements.txt (line 8))
  Using cached scipy-1.17.1-cp312-cp312-win_amd64.whl.metadata (60 kB)
Collecting python-dotenv==1.2.2 (from -r requirements.txt (line 9))
  Using cached python_dotenv-1.2.2-py3-none-any.whl.metadata (27 kB)
Collecting pytest==9.0.3 (from -r requirements-dev.txt (line 4))
  Using cached pytest-9.0.3-py3-none-any.whl.metadata (7.6 kB)
Collecting pytest-cov==7.1.0 (from -r requirements-dev.txt (line 5))
  Using cached pytest_cov-7.1.0-py3-none-any.whl.metadata (32 kB)
Collecting mypy==1.20.2 (from -r requirements-dev.txt (line 8))
  Using cached mypy-1.20.2-cp312-cp312-win_amd64.whl.metadata (2.4 kB)
Collecting ruff==0.15.12 (from -r requirements-dev.txt (line 9))
  Using cached ruff-0.15.12-py3-none-win_amd64.whl.metadata (27 kB)
Collecting ipykernel==7.2.0 (from -r requirements-dev.txt (line 10))
  Using cached ipykernel-7.2.0-py3-none-any.whl.metadata (4.5 kB)
Collecting rustworkx>=0.15.0 (from qiskit==2.4.1->-r requirements.txt (line 3))
  Using cached rustworkx-0.18.1-cp310-abi3-win_amd64.whl.metadata (10 kB)
Collecting dill>=0.3 (from qiskit==2.4.1->-r requirements.txt (line 3))
  Using cached dill-0.4.1-py3-none-any.whl.metadata (10 kB)
Collecting stevedore>=3.0.0 (from qiskit==2.4.1->-r requirements.txt (line 3))
  Using cached stevedore-5.9.1-py3-none-any.whl.metadata (2.3 kB)
Collecting typing-extensions (from qiskit==2.4.1->-r requirements.txt (line 3))
  Using cached typing_extensions-4.16.0-py3-none-any.whl.metadata (3.3 kB)
Collecting psutil>=5 (from qiskit-aer==0.17.2->-r requirements.txt (line 4))
  Using cached psutil-7.2.2-cp37-abi3-win_amd64.whl.metadata (22 kB)
Collecting python-dateutil>=2.8.0 (from qiskit-aer==0.17.2->-r requirements.txt (line 4))
  Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl.metadata (8.4 kB)
Collecting requests>=2.32.4 (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached requests-2.34.2-py3-none-any.whl.metadata (4.8 kB)
Collecting requests-ntlm>=1.1.0 (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached requests_ntlm-1.3.0-py3-none-any.whl.metadata (2.4 kB)
Collecting urllib3>=2.4.0 (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached urllib3-2.7.0-py3-none-any.whl.metadata (6.9 kB)
Collecting ibm-platform-services>=0.55.3 (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached ibm_platform_services-0.77.0-py3-none-any.whl.metadata (9.3 kB)
Collecting ibm-quantum-schemas>=0.5.20260320 (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached ibm_quantum_schemas-0.11.20260824-py3-none-any.whl.metadata (3.1 kB)
Collecting pydantic>=2.7.0 (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Downloading pydantic-2.13.5-py3-none-any.whl.metadata (110 kB)
Collecting packaging (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached packaging-26.3-py3-none-any.whl.metadata (3.5 kB)
Collecting pybase64>=1.4 (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached pybase64-1.5.0-cp312-cp312-win_amd64.whl.metadata (11 kB)
Collecting samplomatic>=0.13.0 (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached samplomatic-0.21.0-py3-none-any.whl.metadata (6.7 kB)
Collecting colorama>=0.4 (from pytest==9.0.3->-r requirements-dev.txt (line 4))
  Using cached colorama-0.4.6-py2.py3-none-any.whl.metadata (17 kB)
Collecting iniconfig>=1.0.1 (from pytest==9.0.3->-r requirements-dev.txt (line 4))
  Using cached iniconfig-2.3.0-py3-none-any.whl.metadata (2.5 kB)
Collecting pluggy<2,>=1.5 (from pytest==9.0.3->-r requirements-dev.txt (line 4))
  Using cached pluggy-1.6.0-py3-none-any.whl.metadata (4.8 kB)
Collecting pygments>=2.7.2 (from pytest==9.0.3->-r requirements-dev.txt (line 4))
  Using cached pygments-2.21.0-py3-none-any.whl.metadata (2.5 kB)
Collecting coverage>=7.10.6 (from coverage[toml]>=7.10.6->pytest-cov==7.1.0->-r requirements-dev.txt (line 5))
  Downloading coverage-7.16.0-cp312-cp312-win_amd64.whl.metadata (8.8 kB)
Collecting mypy_extensions>=1.0.0 (from mypy==1.20.2->-r requirements-dev.txt (line 8))
  Using cached mypy_extensions-1.1.0-py3-none-any.whl.metadata (1.1 kB)
Collecting pathspec>=1.0.0 (from mypy==1.20.2->-r requirements-dev.txt (line 8))
  Using cached pathspec-1.1.1-py3-none-any.whl.metadata (14 kB)
Collecting librt>=0.8.0 (from mypy==1.20.2->-r requirements-dev.txt (line 8))
  Using cached librt-0.15.0-cp312-cp312-win_amd64.whl.metadata (1.3 kB)
Collecting comm>=0.1.1 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached comm-0.2.3-py3-none-any.whl.metadata (3.7 kB)
Collecting debugpy>=1.6.5 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached debugpy-1.8.21-cp312-cp312-win_amd64.whl.metadata (1.5 kB)
Collecting ipython>=7.23.1 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Downloading ipython-9.17.0-py3-none-any.whl.metadata (4.6 kB)
Collecting jupyter-client>=8.8.0 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Downloading jupyter_client-8.10.0-py3-none-any.whl.metadata (8.5 kB)
Collecting jupyter-core!=6.0.*,>=5.1 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached jupyter_core-5.9.1-py3-none-any.whl.metadata (1.5 kB)
Collecting matplotlib-inline>=0.1 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached matplotlib_inline-0.2.2-py3-none-any.whl.metadata (2.4 kB)
Collecting nest-asyncio>=1.4 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached nest_asyncio-1.6.0-py3-none-any.whl.metadata (2.8 kB)
Collecting pyzmq>=25 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached pyzmq-27.2.0-cp312-abi3-win_amd64.whl.metadata (3.8 kB)
Collecting tornado>=6.4.1 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached tornado-6.5.8-cp39-abi3-win_amd64.whl.metadata (2.9 kB)
Collecting traitlets>=5.4.0 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached traitlets-5.16.1-py3-none-any.whl.metadata (10 kB)
Collecting ibm_cloud_sdk_core<4.0.0,>=3.24.4 (from ibm-platform-services>=0.55.3->qiskit-ibm-runtime==0.46.1->-r require
ments.txt (line 5))
  Using cached ibm_cloud_sdk_core-3.26.0-py3-none-any.whl.metadata (8.7 kB)
Collecting PyJWT<3.0.0,>=2.11.0 (from ibm_cloud_sdk_core<4.0.0,>=3.24.4->ibm-platform-services>=0.55.3->qiskit-ibm-runti
me==0.46.1->-r requirements.txt (line 5))
  Using cached pyjwt-2.13.0-py3-none-any.whl.metadata (3.4 kB)
Collecting six>=1.5 (from python-dateutil>=2.8.0->qiskit-aer==0.17.2->-r requirements.txt (line 4))
  Using cached six-1.17.0-py2.py3-none-any.whl.metadata (1.7 kB)
Collecting charset_normalizer<4,>=2 (from requests>=2.32.4->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached charset_normalizer-3.5.1-cp312-cp312-win_amd64.whl.metadata (46 kB)
Collecting idna<4,>=2.5 (from requests>=2.32.4->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached idna-3.19-py3-none-any.whl.metadata (9.2 kB)
Collecting certifi>=2023.5.7 (from requests>=2.32.4->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached certifi-2026.7.22-py3-none-any.whl.metadata (2.5 kB)
Collecting qiskit_qasm3_import<1.0.0,>=0.6.0 (from ibm-quantum-schemas>=0.5.20260320->qiskit-ibm-runtime==0.46.1->-r req
uirements.txt (line 5))
  Using cached qiskit_qasm3_import-0.6.0-py3-none-any.whl.metadata (7.2 kB)
Collecting annotated-types>=0.6.0 (from pydantic>=2.7.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached annotated_types-0.8.0-py3-none-any.whl.metadata (15 kB)
Collecting pydantic-core==2.46.5 (from pydantic>=2.7.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Downloading pydantic_core-2.46.5-cp312-cp312-win_amd64.whl.metadata (6.7 kB)
Collecting typing-inspection>=0.4.2 (from pydantic>=2.7.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached typing_inspection-0.4.4-py3-none-any.whl.metadata (2.6 kB)
Collecting openqasm3<2.0,>=0.4 (from openqasm3[parser]<2.0,>=0.4->qiskit_qasm3_import<1.0.0,>=0.6.0->ibm-quantum-schemas
>=0.5.20260320->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached openqasm3-1.0.1-py3-none-any.whl.metadata (6.0 kB)
Collecting antlr4_python3_runtime<4.14,>=4.7 (from openqasm3[parser]<2.0,>=0.4->qiskit_qasm3_import<1.0.0,>=0.6.0->ibm-q
uantum-schemas>=0.5.20260320->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached antlr4_python3_runtime-4.13.2-py3-none-any.whl.metadata (304 bytes)
Collecting ipython-pygments-lexers>=1.0.0 (from ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached ipython_pygments_lexers-1.1.1-py3-none-any.whl.metadata (1.1 kB)
Collecting jedi>=0.18.2 (from ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached jedi-0.20.0-py2.py3-none-any.whl.metadata (23 kB)
Collecting prompt_toolkit<3.1.0,>=3.0.41 (from ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached prompt_toolkit-3.0.53-py3-none-any.whl.metadata (6.4 kB)
Collecting stack_data>=0.6.0 (from ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached stack_data-0.6.3-py3-none-any.whl.metadata (18 kB)
Collecting wcwidth>=0.1.4 (from prompt_toolkit<3.1.0,>=3.0.41->ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.tx
t (line 10))
  Downloading wcwidth-0.8.3-py3-none-any.whl.metadata (43 kB)
Collecting parso<0.9.0,>=0.8.6 (from jedi>=0.18.2->ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))

  Using cached parso-0.8.7-py2.py3-none-any.whl.metadata (8.2 kB)
Collecting platformdirs>=2.5 (from jupyter-core!=6.0.*,>=5.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Downloading platformdirs-4.11.5-py3-none-any.whl.metadata (5.5 kB)
Collecting cryptography>=1.3 (from requests-ntlm>=1.1.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached cryptography-50.0.1-cp311-abi3-win_amd64.whl.metadata (4.3 kB)
Collecting pyspnego>=0.4.0 (from requests-ntlm>=1.1.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached pyspnego-0.12.2-py3-none-any.whl.metadata (4.2 kB)
Collecting cffi>=2.0.0 (from cryptography>=1.3->requests-ntlm>=1.1.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (l
ine 5))
  Using cached cffi-2.1.1-cp312-cp312-win_amd64.whl.metadata (2.6 kB)
Collecting pycparser (from cffi>=2.0.0->cryptography>=1.3->requests-ntlm>=1.1.0->qiskit-ibm-runtime==0.46.1->-r requirem
ents.txt (line 5))
  Using cached pycparser-3.0-py3-none-any.whl.metadata (8.2 kB)
Collecting sspilib>=0.5.0 (from pyspnego>=0.4.0->requests-ntlm>=1.1.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (
line 5))
  Using cached sspilib-0.6.0-cp311-abi3-win_amd64.whl.metadata (6.9 kB)
Collecting orjson>=3.9.0 (from samplomatic>=0.13.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached orjson-3.12.0-cp312-cp312-win_amd64.whl.metadata (43 kB)
Collecting executing>=1.2.0 (from stack_data>=0.6.0->ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10
))
  Using cached executing-2.2.1-py2.py3-none-any.whl.metadata (8.9 kB)
Collecting asttokens>=2.1.0 (from stack_data>=0.6.0->ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10
))
  Using cached asttokens-3.0.2-py3-none-any.whl.metadata (5.7 kB)
Collecting pure-eval (from stack_data>=0.6.0->ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached pure_eval-0.2.3-py3-none-any.whl.metadata (6.3 kB)
Using cached qiskit-2.4.1-cp310-abi3-win_amd64.whl (9.1 MB)
Using cached numpy-2.4.4-cp312-cp312-win_amd64.whl (12.3 MB)
Using cached qiskit_aer-0.17.2-cp312-cp312-win_amd64.whl (9.6 MB)
Using cached qiskit_ibm_runtime-0.46.1-py3-none-any.whl (1.5 MB)
Using cached scipy-1.17.1-cp312-cp312-win_amd64.whl (36.5 MB)
Using cached python_dotenv-1.2.2-py3-none-any.whl (22 kB)
Using cached pytest-9.0.3-py3-none-any.whl (375 kB)
Using cached pytest_cov-7.1.0-py3-none-any.whl (22 kB)
Using cached mypy-1.20.2-cp312-cp312-win_amd64.whl (10.9 MB)
Using cached ruff-0.15.12-py3-none-win_amd64.whl (11.8 MB)
Using cached ipykernel-7.2.0-py3-none-any.whl (118 kB)
Using cached pluggy-1.6.0-py3-none-any.whl (20 kB)
Using cached colorama-0.4.6-py2.py3-none-any.whl (25 kB)
Using cached comm-0.2.3-py3-none-any.whl (7.3 kB)
Downloading coverage-7.16.0-cp312-cp312-win_amd64.whl (225 kB)
Using cached debugpy-1.8.21-cp312-cp312-win_amd64.whl (5.4 MB)
Using cached dill-0.4.1-py3-none-any.whl (120 kB)
Using cached ibm_platform_services-0.77.0-py3-none-any.whl (412 kB)
Using cached ibm_cloud_sdk_core-3.26.0-py3-none-any.whl (76 kB)
Using cached pyjwt-2.13.0-py3-none-any.whl (31 kB)
Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl (229 kB)
Using cached requests-2.34.2-py3-none-any.whl (73 kB)
Using cached charset_normalizer-3.5.1-cp312-cp312-win_amd64.whl (200 kB)
Using cached idna-3.19-py3-none-any.whl (68 kB)
Using cached urllib3-2.7.0-py3-none-any.whl (131 kB)
Using cached certifi-2026.7.22-py3-none-any.whl (136 kB)
Using cached ibm_quantum_schemas-0.11.20260824-py3-none-any.whl (120 kB)
Downloading pydantic-2.13.5-py3-none-any.whl (472 kB)
Downloading pydantic_core-2.46.5-cp312-cp312-win_amd64.whl (2.0 MB)
   ---------------------------------------- 2.0/2.0 MB 19.2 MB/s  0:00:00
Using cached qiskit_qasm3_import-0.6.0-py3-none-any.whl (29 kB)
Using cached openqasm3-1.0.1-py3-none-any.whl (541 kB)
Using cached antlr4_python3_runtime-4.13.2-py3-none-any.whl (144 kB)
Using cached annotated_types-0.8.0-py3-none-any.whl (13 kB)
Using cached iniconfig-2.3.0-py3-none-any.whl (7.5 kB)
Downloading ipython-9.17.0-py3-none-any.whl (638 kB)
   ---------------------------------------- 638.7/638.7 kB 23.5 MB/s  0:00:00
Using cached prompt_toolkit-3.0.53-py3-none-any.whl (392 kB)
Using cached ipython_pygments_lexers-1.1.1-py3-none-any.whl (8.1 kB)
Using cached jedi-0.20.0-py2.py3-none-any.whl (4.9 MB)
Using cached parso-0.8.7-py2.py3-none-any.whl (107 kB)
Downloading jupyter_client-8.10.0-py3-none-any.whl (110 kB)
Using cached jupyter_core-5.9.1-py3-none-any.whl (29 kB)
Using cached librt-0.15.0-cp312-cp312-win_amd64.whl (126 kB)
Using cached matplotlib_inline-0.2.2-py3-none-any.whl (9.5 kB)
Using cached mypy_extensions-1.1.0-py3-none-any.whl (5.0 kB)
Using cached nest_asyncio-1.6.0-py3-none-any.whl (5.2 kB)
Using cached packaging-26.3-py3-none-any.whl (129 kB)
Using cached pathspec-1.1.1-py3-none-any.whl (57 kB)
Downloading platformdirs-4.11.5-py3-none-any.whl (23 kB)
Using cached psutil-7.2.2-cp37-abi3-win_amd64.whl (137 kB)
Using cached pybase64-1.5.0-cp312-cp312-win_amd64.whl (44 kB)
Using cached pygments-2.21.0-py3-none-any.whl (1.3 MB)
Using cached pyzmq-27.2.0-cp312-abi3-win_amd64.whl (628 kB)
Using cached requests_ntlm-1.3.0-py3-none-any.whl (6.6 kB)
Using cached cryptography-50.0.1-cp311-abi3-win_amd64.whl (3.8 MB)
Using cached cffi-2.1.1-cp312-cp312-win_amd64.whl (185 kB)
Using cached pyspnego-0.12.2-py3-none-any.whl (130 kB)
Using cached rustworkx-0.18.1-cp310-abi3-win_amd64.whl (2.3 MB)
Using cached samplomatic-0.21.0-py3-none-any.whl (234 kB)
Using cached orjson-3.12.0-cp312-cp312-win_amd64.whl (122 kB)
Using cached six-1.17.0-py2.py3-none-any.whl (11 kB)
Using cached sspilib-0.6.0-cp311-abi3-win_amd64.whl (557 kB)
Using cached stack_data-0.6.3-py3-none-any.whl (24 kB)
Using cached asttokens-3.0.2-py3-none-any.whl (28 kB)
Using cached executing-2.2.1-py2.py3-none-any.whl (28 kB)
Using cached stevedore-5.9.1-py3-none-any.whl (54 kB)
Using cached tornado-6.5.8-cp39-abi3-win_amd64.whl (452 kB)
Using cached traitlets-5.16.1-py3-none-any.whl (86 kB)
Using cached typing_extensions-4.16.0-py3-none-any.whl (45 kB)
Using cached typing_inspection-0.4.4-py3-none-any.whl (14 kB)
Downloading wcwidth-0.8.3-py3-none-any.whl (331 kB)
Using cached pure_eval-0.2.3-py3-none-any.whl (11 kB)
Using cached pycparser-3.0-py3-none-any.whl (48 kB)
Installing collected packages: pure-eval, openqasm3, antlr4_python3_runtime, wcwidth, urllib3, typing-extensions, traitl
ets, tornado, stevedore, sspilib, six, ruff, pyzmq, python-dotenv, PyJWT, pygments, pycparser, pybase64, psutil, pluggy,
 platformdirs, pathspec, parso, packaging, orjson, numpy, nest-asyncio, mypy_extensions, librt, iniconfig, idna, executi
ng, dill, debugpy, coverage, comm, colorama, charset_normalizer, certifi, asttokens, annotated-types, typing-inspection,
 stack_data, scipy, rustworkx, requests, python-dateutil, pytest, pydantic-core, prompt_toolkit, mypy, matplotlib-inline
, jupyter-core, jedi, ipython-pygments-lexers, cffi, qiskit, pytest-cov, pydantic, jupyter-client, ipython, ibm_cloud_sd
k_core, cryptography, samplomatic, qiskit_qasm3_import, qiskit-aer, pyspnego, ipykernel, ibm-platform-services, requests
-ntlm, ibm-quantum-schemas, qiskit-ibm-runtime
Successfully installed PyJWT-2.13.0 annotated-types-0.8.0 antlr4_python3_runtime-4.13.2 asttokens-3.0.2 certifi-2026.7.2
2 cffi-2.1.1 charset_normalizer-3.5.1 colorama-0.4.6 comm-0.2.3 coverage-7.16.0 cryptography-50.0.1 debugpy-1.8.21 dill-
0.4.1 executing-2.2.1 ibm-platform-services-0.77.0 ibm-quantum-schemas-0.11.20260824 ibm_cloud_sdk_core-3.26.0 idna-3.19
 iniconfig-2.3.0 ipykernel-7.2.0 ipython-9.17.0 ipython-pygments-lexers-1.1.1 jedi-0.20.0 jupyter-client-8.10.0 jupyter-
core-5.9.1 librt-0.15.0 matplotlib-inline-0.2.2 mypy-1.20.2 mypy_extensions-1.1.0 nest-asyncio-1.6.0 numpy-2.4.4 openqas
m3-1.0.1 orjson-3.12.0 packaging-26.3 parso-0.8.7 pathspec-1.1.1 platformdirs-4.11.5 pluggy-1.6.0 prompt_toolkit-3.0.53
psutil-7.2.2 pure-eval-0.2.3 pybase64-1.5.0 pycparser-3.0 pydantic-2.13.5 pydantic-core-2.46.5 pygments-2.21.0 pyspnego-
0.12.2 pytest-9.0.3 pytest-cov-7.1.0 python-dateutil-2.9.0.post0 python-dotenv-1.2.2 pyzmq-27.2.0 qiskit-2.4.1 qiskit-ae
r-0.17.2 qiskit-ibm-runtime-0.46.1 qiskit_qasm3_import-0.6.0 requests-2.34.2 requests-ntlm-1.3.0 ruff-0.15.12 rustworkx-
0.18.1 samplomatic-0.21.0 scipy-1.17.1 six-1.17.0 sspilib-0.6.0 stack_data-0.6.3 stevedore-5.9.1 tornado-6.5.8 traitlets
-5.16.1 typing-extensions-4.16.0 typing-inspection-0.4.4 urllib3-2.7.0 wcwidth-0.8.3
Obtaining file:///C:/scted-verify/pr44
  Installing build dependencies ... done
  Checking if build backend supports build_editable ... done
  Getting requirements to build editable ... done
  Installing backend dependencies ... done
  Preparing editable metadata (pyproject.toml) ... done
Building wheels for collected packages: superconducted
  Building editable for superconducted (pyproject.toml) ... done
  Created wheel for superconducted: filename=superconducted-0.1.0-py3-none-any.whl size=5082 sha256=f1a571c569e03e0d6318
0b3b45ecfe8ff7b0b1596036e19fa6f3f909d6e562fa
  Stored in directory: C:\Users\PC\AppData\Local\Temp\pip-ephem-wheel-cache-s2tt43zs\wheels\dd\89\99\455bee37bb7bec3240d
127db58a3526feeec3525a5df92b9ec
Successfully built superconducted
Installing collected packages: superconducted
Successfully installed superconducted-0.1.0
PS C:\scted-verify\pr44>
(.venv) python --version
(Get-CimInstance Win32_OperatingSystem).Caption
(Get-CimInstance Win32_OperatingSystem).Version
(Get-CimInstance Win32_Processor).Name
[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
pip freeze
Python 3.12.10
Microsoft Windows 10 Home
10.0.19045
AMD Ryzen 5 5500
15,9
annotated-types==0.8.0
antlr4-python3-runtime==4.13.2
asttokens==3.0.2
certifi==2026.7.22
cffi==2.1.1
charset-normalizer==3.5.1
colorama==0.4.6
comm==0.2.3
coverage==7.16.0
cryptography==50.0.1
debugpy==1.8.21
dill==0.4.1
executing==2.2.1
ibm-cloud-sdk-core==3.26.0
ibm-platform-services==0.77.0
ibm-quantum-schemas==0.11.20260824
idna==3.19
iniconfig==2.3.0
ipykernel==7.2.0
ipython==9.17.0
ipython_pygments_lexers==1.1.1
jedi==0.20.0
jupyter_client==8.10.0
jupyter_core==5.9.1
librt==0.15.0
matplotlib-inline==0.2.2
mypy==1.20.2
mypy_extensions==1.1.0
nest-asyncio==1.6.0
numpy==2.4.4
openqasm3==1.0.1
orjson==3.12.0
packaging==26.3
parso==0.8.7
pathspec==1.1.1
platformdirs==4.11.5
pluggy==1.6.0
prompt_toolkit==3.0.53
psutil==7.2.2
pure_eval==0.2.3
pybase64==1.5.0
pycparser==3.0
pydantic==2.13.5
pydantic_core==2.46.5
Pygments==2.21.0
PyJWT==2.13.0
pyspnego==0.12.2
pytest==9.0.3
pytest-cov==7.1.0
python-dateutil==2.9.0.post0
python-dotenv==1.2.2
pyzmq==27.2.0
qiskit==2.4.1
qiskit-aer==0.17.2
qiskit-ibm-runtime==0.46.1
qiskit-qasm3-import==0.6.0
requests==2.34.2
requests_ntlm==1.3.0
ruff==0.15.12
rustworkx==0.18.1
samplomatic==0.21.0
scipy==1.17.1
six==1.17.0
sspilib==0.6.0
stack-data==0.6.3
stevedore==5.9.1
-e git+https://github.com/SuperconducTED/superconducted-noise-engine.git@7fc95bb45c21adacdac957882881c0c00fb4aea6#egg=su
perconducted
tornado==6.5.8
traitlets==5.16.1
typing-inspection==0.4.4
typing_extensions==4.16.0
urllib3==2.7.0
wcwidth==0.8.3
PS C:\scted-verify\pr44>
(.venv) python -m ruff check .
python -m ruff format --check .
python -m mypy --strict src/superconducted
python -m pytest tests/ -q
All checks passed!
36 files already formatted
Success: no issues found in 22 source files
Windows PowerShell
Copyright (C) Microsoft Corporation. All rights reserved.

Try the new cross-platform PowerShell https://aka.ms/pscore6

PS C:\Users\PC> git --version
>> python --version
git version 2.55.0.windows.3
Python 3.12.10
PS C:\Users\PC> New-Item -ItemType Directory -Force C:\scted-verify | Out-Null
>> Set-Location C:\scted-verify
>> $env:NO_COLOR = "1"
>> Start-Transcript -Path C:\scted-verify\pr44-transcript.txt
Transcript started, output file is C:\scted-verify\pr44-transcript.txt
PS C:\scted-verify> git clone https://github.com/SuperconducTED/superconducted-noise-engine.git pr44
>> Set-Location C:\scted-verify\pr44
Cloning into 'pr44'...
remote: Enumerating objects: 8532, done.
remote: Counting objects: 100% (308/308), done.
remote: Compressing objects: 100% (194/194), done.
remote: Total 8532 (delta 173), reused 149 (delta 110), pack-reused 8224 (from 2)
Receiving objects: 100% (8532/8532), 44.46 MiB | 22.75 MiB/s, done.
Resolving deltas: 100% (5100/5100), done.
PS C:\scted-verify\pr44> git checkout feature/mert-issue-35-consequent-degeneracy
>> git rev-parse HEAD
branch 'feature/mert-issue-35-consequent-degeneracy' set up to track 'origin/feature/mert-issue-35-consequent-degeneracy'.
Switched to a new branch 'feature/mert-issue-35-consequent-degeneracy'
7fc95bb45c21adacdac957882881c0c00fb4aea6
PS C:\scted-verify\pr44> git log --oneline -4
7fc95bb (HEAD -> feature/mert-issue-35-consequent-degeneracy, origin/feature/mert-issue-35-consequent-degeneracy) docs: carry the desktop runbook into the implementation doc
5b36de0 docs: stamp NC-021 with the commit its 187 was measured at
571ffbc feat(integration): ship the channel-viability contract — ADR-024 (Closes #35)
9792017 (origin/main, origin/HEAD, main) Merge pull request #43 from SuperconducTED/chore/lf-renormalization
PS C:\scted-verify\pr44> python -m venv .venv
>> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
>> .\.venv\Scripts\Activate.ps1
(.venv) PS C:\scted-verify\pr44> python -m pip install --upgrade pip
>> pip install -r requirements.txt -r requirements-dev.txt
>> pip install -e . --no-deps
Requirement already satisfied: pip in c:\scted-verify\pr44\.venv\lib\site-packages (25.0.1)
Collecting pip
  Using cached pip-26.2.1-py3-none-any.whl.metadata (4.6 kB)
Using cached pip-26.2.1-py3-none-any.whl (1.8 MB)
Installing collected packages: pip
  Attempting uninstall: pip
    Found existing installation: pip 25.0.1
    Uninstalling pip-25.0.1:
      Successfully uninstalled pip-25.0.1
Successfully installed pip-26.2.1
Collecting qiskit==2.4.1 (from -r requirements.txt (line 3))
  Using cached qiskit-2.4.1-cp310-abi3-win_amd64.whl.metadata (13 kB)
Collecting qiskit-aer==0.17.2 (from -r requirements.txt (line 4))
  Using cached qiskit_aer-0.17.2-cp312-cp312-win_amd64.whl.metadata (8.5 kB)
Collecting qiskit-ibm-runtime==0.46.1 (from -r requirements.txt (line 5))
  Using cached qiskit_ibm_runtime-0.46.1-py3-none-any.whl.metadata (21 kB)
Collecting numpy==2.4.4 (from -r requirements.txt (line 7))
  Using cached numpy-2.4.4-cp312-cp312-win_amd64.whl.metadata (6.6 kB)
Collecting scipy==1.17.1 (from -r requirements.txt (line 8))
  Using cached scipy-1.17.1-cp312-cp312-win_amd64.whl.metadata (60 kB)
Collecting python-dotenv==1.2.2 (from -r requirements.txt (line 9))
  Using cached python_dotenv-1.2.2-py3-none-any.whl.metadata (27 kB)
Collecting pytest==9.0.3 (from -r requirements-dev.txt (line 4))
  Using cached pytest-9.0.3-py3-none-any.whl.metadata (7.6 kB)
Collecting pytest-cov==7.1.0 (from -r requirements-dev.txt (line 5))
  Using cached pytest_cov-7.1.0-py3-none-any.whl.metadata (32 kB)
Collecting mypy==1.20.2 (from -r requirements-dev.txt (line 8))
  Using cached mypy-1.20.2-cp312-cp312-win_amd64.whl.metadata (2.4 kB)
Collecting ruff==0.15.12 (from -r requirements-dev.txt (line 9))
  Using cached ruff-0.15.12-py3-none-win_amd64.whl.metadata (27 kB)
Collecting ipykernel==7.2.0 (from -r requirements-dev.txt (line 10))
  Using cached ipykernel-7.2.0-py3-none-any.whl.metadata (4.5 kB)
Collecting rustworkx>=0.15.0 (from qiskit==2.4.1->-r requirements.txt (line 3))
  Using cached rustworkx-0.18.1-cp310-abi3-win_amd64.whl.metadata (10 kB)
Collecting dill>=0.3 (from qiskit==2.4.1->-r requirements.txt (line 3))
  Using cached dill-0.4.1-py3-none-any.whl.metadata (10 kB)
Collecting stevedore>=3.0.0 (from qiskit==2.4.1->-r requirements.txt (line 3))
  Using cached stevedore-5.9.1-py3-none-any.whl.metadata (2.3 kB)
Collecting typing-extensions (from qiskit==2.4.1->-r requirements.txt (line 3))
  Using cached typing_extensions-4.16.0-py3-none-any.whl.metadata (3.3 kB)
Collecting psutil>=5 (from qiskit-aer==0.17.2->-r requirements.txt (line 4))
  Using cached psutil-7.2.2-cp37-abi3-win_amd64.whl.metadata (22 kB)
Collecting python-dateutil>=2.8.0 (from qiskit-aer==0.17.2->-r requirements.txt (line 4))
  Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl.metadata (8.4 kB)
Collecting requests>=2.32.4 (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached requests-2.34.2-py3-none-any.whl.metadata (4.8 kB)
Collecting requests-ntlm>=1.1.0 (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached requests_ntlm-1.3.0-py3-none-any.whl.metadata (2.4 kB)
Collecting urllib3>=2.4.0 (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached urllib3-2.7.0-py3-none-any.whl.metadata (6.9 kB)
Collecting ibm-platform-services>=0.55.3 (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached ibm_platform_services-0.77.0-py3-none-any.whl.metadata (9.3 kB)
Collecting ibm-quantum-schemas>=0.5.20260320 (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached ibm_quantum_schemas-0.11.20260824-py3-none-any.whl.metadata (3.1 kB)
Collecting pydantic>=2.7.0 (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Downloading pydantic-2.13.5-py3-none-any.whl.metadata (110 kB)
Collecting packaging (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached packaging-26.3-py3-none-any.whl.metadata (3.5 kB)
Collecting pybase64>=1.4 (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached pybase64-1.5.0-cp312-cp312-win_amd64.whl.metadata (11 kB)
Collecting samplomatic>=0.13.0 (from qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached samplomatic-0.21.0-py3-none-any.whl.metadata (6.7 kB)
Collecting colorama>=0.4 (from pytest==9.0.3->-r requirements-dev.txt (line 4))
  Using cached colorama-0.4.6-py2.py3-none-any.whl.metadata (17 kB)
Collecting iniconfig>=1.0.1 (from pytest==9.0.3->-r requirements-dev.txt (line 4))
  Using cached iniconfig-2.3.0-py3-none-any.whl.metadata (2.5 kB)
Collecting pluggy<2,>=1.5 (from pytest==9.0.3->-r requirements-dev.txt (line 4))
  Using cached pluggy-1.6.0-py3-none-any.whl.metadata (4.8 kB)
Collecting pygments>=2.7.2 (from pytest==9.0.3->-r requirements-dev.txt (line 4))
  Using cached pygments-2.21.0-py3-none-any.whl.metadata (2.5 kB)
Collecting coverage>=7.10.6 (from coverage[toml]>=7.10.6->pytest-cov==7.1.0->-r requirements-dev.txt (line 5))
  Downloading coverage-7.16.0-cp312-cp312-win_amd64.whl.metadata (8.8 kB)
Collecting mypy_extensions>=1.0.0 (from mypy==1.20.2->-r requirements-dev.txt (line 8))
  Using cached mypy_extensions-1.1.0-py3-none-any.whl.metadata (1.1 kB)
Collecting pathspec>=1.0.0 (from mypy==1.20.2->-r requirements-dev.txt (line 8))
  Using cached pathspec-1.1.1-py3-none-any.whl.metadata (14 kB)
Collecting librt>=0.8.0 (from mypy==1.20.2->-r requirements-dev.txt (line 8))
  Using cached librt-0.15.0-cp312-cp312-win_amd64.whl.metadata (1.3 kB)
Collecting comm>=0.1.1 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached comm-0.2.3-py3-none-any.whl.metadata (3.7 kB)
Collecting debugpy>=1.6.5 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached debugpy-1.8.21-cp312-cp312-win_amd64.whl.metadata (1.5 kB)
Collecting ipython>=7.23.1 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Downloading ipython-9.17.0-py3-none-any.whl.metadata (4.6 kB)
Collecting jupyter-client>=8.8.0 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Downloading jupyter_client-8.10.0-py3-none-any.whl.metadata (8.5 kB)
Collecting jupyter-core!=6.0.*,>=5.1 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached jupyter_core-5.9.1-py3-none-any.whl.metadata (1.5 kB)
Collecting matplotlib-inline>=0.1 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached matplotlib_inline-0.2.2-py3-none-any.whl.metadata (2.4 kB)
Collecting nest-asyncio>=1.4 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached nest_asyncio-1.6.0-py3-none-any.whl.metadata (2.8 kB)
Collecting pyzmq>=25 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached pyzmq-27.2.0-cp312-abi3-win_amd64.whl.metadata (3.8 kB)
Collecting tornado>=6.4.1 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached tornado-6.5.8-cp39-abi3-win_amd64.whl.metadata (2.9 kB)
Collecting traitlets>=5.4.0 (from ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached traitlets-5.16.1-py3-none-any.whl.metadata (10 kB)
Collecting ibm_cloud_sdk_core<4.0.0,>=3.24.4 (from ibm-platform-services>=0.55.3->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached ibm_cloud_sdk_core-3.26.0-py3-none-any.whl.metadata (8.7 kB)
Collecting PyJWT<3.0.0,>=2.11.0 (from ibm_cloud_sdk_core<4.0.0,>=3.24.4->ibm-platform-services>=0.55.3->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached pyjwt-2.13.0-py3-none-any.whl.metadata (3.4 kB)
Collecting six>=1.5 (from python-dateutil>=2.8.0->qiskit-aer==0.17.2->-r requirements.txt (line 4))
  Using cached six-1.17.0-py2.py3-none-any.whl.metadata (1.7 kB)
Collecting charset_normalizer<4,>=2 (from requests>=2.32.4->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached charset_normalizer-3.5.1-cp312-cp312-win_amd64.whl.metadata (46 kB)
Collecting idna<4,>=2.5 (from requests>=2.32.4->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached idna-3.19-py3-none-any.whl.metadata (9.2 kB)
Collecting certifi>=2023.5.7 (from requests>=2.32.4->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached certifi-2026.7.22-py3-none-any.whl.metadata (2.5 kB)
Collecting qiskit_qasm3_import<1.0.0,>=0.6.0 (from ibm-quantum-schemas>=0.5.20260320->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached qiskit_qasm3_import-0.6.0-py3-none-any.whl.metadata (7.2 kB)
Collecting annotated-types>=0.6.0 (from pydantic>=2.7.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached annotated_types-0.8.0-py3-none-any.whl.metadata (15 kB)
Collecting pydantic-core==2.46.5 (from pydantic>=2.7.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Downloading pydantic_core-2.46.5-cp312-cp312-win_amd64.whl.metadata (6.7 kB)
Collecting typing-inspection>=0.4.2 (from pydantic>=2.7.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached typing_inspection-0.4.4-py3-none-any.whl.metadata (2.6 kB)
Collecting openqasm3<2.0,>=0.4 (from openqasm3[parser]<2.0,>=0.4->qiskit_qasm3_import<1.0.0,>=0.6.0->ibm-quantum-schemas>=0.5.20260320->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached openqasm3-1.0.1-py3-none-any.whl.metadata (6.0 kB)
Collecting antlr4_python3_runtime<4.14,>=4.7 (from openqasm3[parser]<2.0,>=0.4->qiskit_qasm3_import<1.0.0,>=0.6.0->ibm-quantum-schemas>=0.5.20260320->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached antlr4_python3_runtime-4.13.2-py3-none-any.whl.metadata (304 bytes)
Collecting ipython-pygments-lexers>=1.0.0 (from ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached ipython_pygments_lexers-1.1.1-py3-none-any.whl.metadata (1.1 kB)
Collecting jedi>=0.18.2 (from ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached jedi-0.20.0-py2.py3-none-any.whl.metadata (23 kB)
Collecting prompt_toolkit<3.1.0,>=3.0.41 (from ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached prompt_toolkit-3.0.53-py3-none-any.whl.metadata (6.4 kB)
Collecting stack_data>=0.6.0 (from ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached stack_data-0.6.3-py3-none-any.whl.metadata (18 kB)
Collecting wcwidth>=0.1.4 (from prompt_toolkit<3.1.0,>=3.0.41->ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Downloading wcwidth-0.8.3-py3-none-any.whl.metadata (43 kB)
Collecting parso<0.9.0,>=0.8.6 (from jedi>=0.18.2->ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached parso-0.8.7-py2.py3-none-any.whl.metadata (8.2 kB)
Collecting platformdirs>=2.5 (from jupyter-core!=6.0.*,>=5.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Downloading platformdirs-4.11.5-py3-none-any.whl.metadata (5.5 kB)
Collecting cryptography>=1.3 (from requests-ntlm>=1.1.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached cryptography-50.0.1-cp311-abi3-win_amd64.whl.metadata (4.3 kB)
Collecting pyspnego>=0.4.0 (from requests-ntlm>=1.1.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached pyspnego-0.12.2-py3-none-any.whl.metadata (4.2 kB)
Collecting cffi>=2.0.0 (from cryptography>=1.3->requests-ntlm>=1.1.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached cffi-2.1.1-cp312-cp312-win_amd64.whl.metadata (2.6 kB)
Collecting pycparser (from cffi>=2.0.0->cryptography>=1.3->requests-ntlm>=1.1.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached pycparser-3.0-py3-none-any.whl.metadata (8.2 kB)
Collecting sspilib>=0.5.0 (from pyspnego>=0.4.0->requests-ntlm>=1.1.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached sspilib-0.6.0-cp311-abi3-win_amd64.whl.metadata (6.9 kB)
Collecting orjson>=3.9.0 (from samplomatic>=0.13.0->qiskit-ibm-runtime==0.46.1->-r requirements.txt (line 5))
  Using cached orjson-3.12.0-cp312-cp312-win_amd64.whl.metadata (43 kB)
Collecting executing>=1.2.0 (from stack_data>=0.6.0->ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached executing-2.2.1-py2.py3-none-any.whl.metadata (8.9 kB)
Collecting asttokens>=2.1.0 (from stack_data>=0.6.0->ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached asttokens-3.0.2-py3-none-any.whl.metadata (5.7 kB)
Collecting pure-eval (from stack_data>=0.6.0->ipython>=7.23.1->ipykernel==7.2.0->-r requirements-dev.txt (line 10))
  Using cached pure_eval-0.2.3-py3-none-any.whl.metadata (6.3 kB)
Using cached qiskit-2.4.1-cp310-abi3-win_amd64.whl (9.1 MB)
Using cached numpy-2.4.4-cp312-cp312-win_amd64.whl (12.3 MB)
Using cached qiskit_aer-0.17.2-cp312-cp312-win_amd64.whl (9.6 MB)
Using cached qiskit_ibm_runtime-0.46.1-py3-none-any.whl (1.5 MB)
Using cached scipy-1.17.1-cp312-cp312-win_amd64.whl (36.5 MB)
Using cached python_dotenv-1.2.2-py3-none-any.whl (22 kB)
Using cached pytest-9.0.3-py3-none-any.whl (375 kB)
Using cached pytest_cov-7.1.0-py3-none-any.whl (22 kB)
Using cached mypy-1.20.2-cp312-cp312-win_amd64.whl (10.9 MB)
Using cached ruff-0.15.12-py3-none-win_amd64.whl (11.8 MB)
Using cached ipykernel-7.2.0-py3-none-any.whl (118 kB)
Using cached pluggy-1.6.0-py3-none-any.whl (20 kB)
Using cached colorama-0.4.6-py2.py3-none-any.whl (25 kB)
Using cached comm-0.2.3-py3-none-any.whl (7.3 kB)
Downloading coverage-7.16.0-cp312-cp312-win_amd64.whl (225 kB)
Using cached debugpy-1.8.21-cp312-cp312-win_amd64.whl (5.4 MB)
Using cached dill-0.4.1-py3-none-any.whl (120 kB)
Using cached ibm_platform_services-0.77.0-py3-none-any.whl (412 kB)
Using cached ibm_cloud_sdk_core-3.26.0-py3-none-any.whl (76 kB)
Using cached pyjwt-2.13.0-py3-none-any.whl (31 kB)
Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl (229 kB)
Using cached requests-2.34.2-py3-none-any.whl (73 kB)
Using cached charset_normalizer-3.5.1-cp312-cp312-win_amd64.whl (200 kB)
Using cached idna-3.19-py3-none-any.whl (68 kB)
Using cached urllib3-2.7.0-py3-none-any.whl (131 kB)
Using cached certifi-2026.7.22-py3-none-any.whl (136 kB)
Using cached ibm_quantum_schemas-0.11.20260824-py3-none-any.whl (120 kB)
Downloading pydantic-2.13.5-py3-none-any.whl (472 kB)
Downloading pydantic_core-2.46.5-cp312-cp312-win_amd64.whl (2.0 MB)
   ---------------------------------------- 2.0/2.0 MB 19.2 MB/s  0:00:00
Using cached qiskit_qasm3_import-0.6.0-py3-none-any.whl (29 kB)
Using cached openqasm3-1.0.1-py3-none-any.whl (541 kB)
Using cached antlr4_python3_runtime-4.13.2-py3-none-any.whl (144 kB)
Using cached annotated_types-0.8.0-py3-none-any.whl (13 kB)
Using cached iniconfig-2.3.0-py3-none-any.whl (7.5 kB)
Downloading ipython-9.17.0-py3-none-any.whl (638 kB)
   ---------------------------------------- 638.7/638.7 kB 23.5 MB/s  0:00:00
Using cached prompt_toolkit-3.0.53-py3-none-any.whl (392 kB)
Using cached ipython_pygments_lexers-1.1.1-py3-none-any.whl (8.1 kB)
Using cached jedi-0.20.0-py2.py3-none-any.whl (4.9 MB)
Using cached parso-0.8.7-py2.py3-none-any.whl (107 kB)
Downloading jupyter_client-8.10.0-py3-none-any.whl (110 kB)
Using cached jupyter_core-5.9.1-py3-none-any.whl (29 kB)
Using cached librt-0.15.0-cp312-cp312-win_amd64.whl (126 kB)
Using cached matplotlib_inline-0.2.2-py3-none-any.whl (9.5 kB)
Using cached mypy_extensions-1.1.0-py3-none-any.whl (5.0 kB)
Using cached nest_asyncio-1.6.0-py3-none-any.whl (5.2 kB)
Using cached packaging-26.3-py3-none-any.whl (129 kB)
Using cached pathspec-1.1.1-py3-none-any.whl (57 kB)
Downloading platformdirs-4.11.5-py3-none-any.whl (23 kB)
Using cached psutil-7.2.2-cp37-abi3-win_amd64.whl (137 kB)
Using cached pybase64-1.5.0-cp312-cp312-win_amd64.whl (44 kB)
Using cached pygments-2.21.0-py3-none-any.whl (1.3 MB)
Using cached pyzmq-27.2.0-cp312-abi3-win_amd64.whl (628 kB)
Using cached requests_ntlm-1.3.0-py3-none-any.whl (6.6 kB)
Using cached cryptography-50.0.1-cp311-abi3-win_amd64.whl (3.8 MB)
Using cached cffi-2.1.1-cp312-cp312-win_amd64.whl (185 kB)
Using cached pyspnego-0.12.2-py3-none-any.whl (130 kB)
Using cached rustworkx-0.18.1-cp310-abi3-win_amd64.whl (2.3 MB)
Using cached samplomatic-0.21.0-py3-none-any.whl (234 kB)
Using cached orjson-3.12.0-cp312-cp312-win_amd64.whl (122 kB)
Using cached six-1.17.0-py2.py3-none-any.whl (11 kB)
Using cached sspilib-0.6.0-cp311-abi3-win_amd64.whl (557 kB)
Using cached stack_data-0.6.3-py3-none-any.whl (24 kB)
Using cached asttokens-3.0.2-py3-none-any.whl (28 kB)
Using cached executing-2.2.1-py2.py3-none-any.whl (28 kB)
Using cached stevedore-5.9.1-py3-none-any.whl (54 kB)
Using cached tornado-6.5.8-cp39-abi3-win_amd64.whl (452 kB)
Using cached traitlets-5.16.1-py3-none-any.whl (86 kB)
Using cached typing_extensions-4.16.0-py3-none-any.whl (45 kB)
Using cached typing_inspection-0.4.4-py3-none-any.whl (14 kB)
Downloading wcwidth-0.8.3-py3-none-any.whl (331 kB)
Using cached pure_eval-0.2.3-py3-none-any.whl (11 kB)
Using cached pycparser-3.0-py3-none-any.whl (48 kB)
Installing collected packages: pure-eval, openqasm3, antlr4_python3_runtime, wcwidth, urllib3, typing-extensions, traitlets, tornado, stevedore, sspilib, six, ruff, pyzmq, python-dotenv, PyJWT, pygments, pycparser, pybase64, psutil, pluggy, platformdirs, pathspec, parso,
 packaging, orjson, numpy, nest-asyncio, mypy_extensions, librt, iniconfig, idna, executing, dill, debugpy, coverage, comm, colorama, charset_normalizer, certifi, asttokens, annotated-types, typing-inspection, stack_data, scipy, rustworkx, requests, python-dateutil, pyte
st, pydantic-core, prompt_toolkit, mypy, matplotlib-inline, jupyter-core, jedi, ipython-pygments-lexers, cffi, qiskit, pytest-cov, pydantic, jupyter-client, ipython, ibm_cloud_sdk_core, cryptography, samplomatic, qiskit_qasm3_import, qiskit-aer, pyspnego, ipykernel, ibm-
platform-services, requests-ntlm, ibm-quantum-schemas, qiskit-ibm-runtime
Successfully installed PyJWT-2.13.0 annotated-types-0.8.0 antlr4_python3_runtime-4.13.2 asttokens-3.0.2 certifi-2026.7.22 cffi-2.1.1 charset_normalizer-3.5.1 colorama-0.4.6 comm-0.2.3 coverage-7.16.0 cryptography-50.0.1 debugpy-1.8.21 dill-0.4.1 executing-2.2.1 ibm-platf
orm-services-0.77.0 ibm-quantum-schemas-0.11.20260824 ibm_cloud_sdk_core-3.26.0 idna-3.19 iniconfig-2.3.0 ipykernel-7.2.0 ipython-9.17.0 ipython-pygments-lexers-1.1.1 jedi-0.20.0 jupyter-client-8.10.0 jupyter-core-5.9.1 librt-0.15.0 matplotlib-inline-0.2.2 mypy-1.20.2 my
py_extensions-1.1.0 nest-asyncio-1.6.0 numpy-2.4.4 openqasm3-1.0.1 orjson-3.12.0 packaging-26.3 parso-0.8.7 pathspec-1.1.1 platformdirs-4.11.5 pluggy-1.6.0 prompt_toolkit-3.0.53 psutil-7.2.2 pure-eval-0.2.3 pybase64-1.5.0 pycparser-3.0 pydantic-2.13.5 pydantic-core-2.46.
5 pygments-2.21.0 pyspnego-0.12.2 pytest-9.0.3 pytest-cov-7.1.0 python-dateutil-2.9.0.post0 python-dotenv-1.2.2 pyzmq-27.2.0 qiskit-2.4.1 qiskit-aer-0.17.2 qiskit-ibm-runtime-0.46.1 qiskit_qasm3_import-0.6.0 requests-2.34.2 requests-ntlm-1.3.0 ruff-0.15.12 rustworkx-0.18
.1 samplomatic-0.21.0 scipy-1.17.1 six-1.17.0 sspilib-0.6.0 stack_data-0.6.3 stevedore-5.9.1 tornado-6.5.8 traitlets-5.16.1 typing-extensions-4.16.0 typing-inspection-0.4.4 urllib3-2.7.0 wcwidth-0.8.3
Obtaining file:///C:/scted-verify/pr44
  Installing build dependencies ... done
  Checking if build backend supports build_editable ... done
  Getting requirements to build editable ... done
  Installing backend dependencies ... done
  Preparing editable metadata (pyproject.toml) ... done
Building wheels for collected packages: superconducted
  Building editable for superconducted (pyproject.toml) ... done
  Created wheel for superconducted: filename=superconducted-0.1.0-py3-none-any.whl size=5082 sha256=f1a571c569e03e0d63180b3b45ecfe8ff7b0b1596036e19fa6f3f909d6e562fa
  Stored in directory: C:\Users\PC\AppData\Local\Temp\pip-ephem-wheel-cache-s2tt43zs\wheels\dd\89\99\455bee37bb7bec3240d127db58a3526feeec3525a5df92b9ec
Successfully built superconducted
Installing collected packages: superconducted
Successfully installed superconducted-0.1.0
(.venv) PS C:\scted-verify\pr44> python --version
>> (Get-CimInstance Win32_OperatingSystem).Caption
>> (Get-CimInstance Win32_OperatingSystem).Version
>> (Get-CimInstance Win32_Processor).Name
>> [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
>> pip freeze
Python 3.12.10
Microsoft Windows 10 Home
10.0.19045
AMD Ryzen 5 5500
15,9
annotated-types==0.8.0
antlr4-python3-runtime==4.13.2
asttokens==3.0.2
certifi==2026.7.22
cffi==2.1.1
charset-normalizer==3.5.1
colorama==0.4.6
comm==0.2.3
coverage==7.16.0
cryptography==50.0.1
debugpy==1.8.21
dill==0.4.1
executing==2.2.1
ibm-cloud-sdk-core==3.26.0
ibm-platform-services==0.77.0
ibm-quantum-schemas==0.11.20260824
idna==3.19
iniconfig==2.3.0
ipykernel==7.2.0
ipython==9.17.0
ipython_pygments_lexers==1.1.1
jedi==0.20.0
jupyter_client==8.10.0
jupyter_core==5.9.1
librt==0.15.0
matplotlib-inline==0.2.2
mypy==1.20.2
mypy_extensions==1.1.0
nest-asyncio==1.6.0
numpy==2.4.4
openqasm3==1.0.1
orjson==3.12.0
packaging==26.3
parso==0.8.7
pathspec==1.1.1
platformdirs==4.11.5
pluggy==1.6.0
prompt_toolkit==3.0.53
psutil==7.2.2
pure_eval==0.2.3
pybase64==1.5.0
pycparser==3.0
pydantic==2.13.5
pydantic_core==2.46.5
Pygments==2.21.0
PyJWT==2.13.0
pyspnego==0.12.2
pytest==9.0.3
pytest-cov==7.1.0
python-dateutil==2.9.0.post0
python-dotenv==1.2.2
pyzmq==27.2.0
qiskit==2.4.1
qiskit-aer==0.17.2
qiskit-ibm-runtime==0.46.1
qiskit-qasm3-import==0.6.0
requests==2.34.2
requests_ntlm==1.3.0
ruff==0.15.12
rustworkx==0.18.1
samplomatic==0.21.0
scipy==1.17.1
six==1.17.0
sspilib==0.6.0
stack-data==0.6.3
stevedore==5.9.1
-e git+https://github.com/SuperconducTED/superconducted-noise-engine.git@7fc95bb45c21adacdac957882881c0c00fb4aea6#egg=superconducted
tornado==6.5.8
traitlets==5.16.1
typing-inspection==0.4.4
typing_extensions==4.16.0
urllib3==2.7.0
wcwidth==0.8.3
(.venv) PS C:\scted-verify\pr44> python -m ruff check .
>> python -m ruff format --check .
>> python -m mypy --strict src/superconducted
>> python -m pytest tests/ -q
All checks passed!
36 files already formatted
Success: no issues found in 22 source files
================================================= test session starts =================================================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\scted-verify\pr44
configfile: pyproject.toml
plugins: cov-7.1.0
collected 187 items

tests\calibration\test_features_missing_fields.py ......                                                         [  3%]
tests\calibration\test_loader.py .................                                                               [ 12%]
tests\test_calibration.py ...............................                                                        [ 28%]
tests\test_channel_viability.py .....................                                                            [ 40%]
tests\test_first_ensemble_run.py ..................                                                                                                                                                                                                                     [ 49%]
tests\test_interfaces.py ...........................                                                                                                                                                                                                                    [ 64%]
tests\test_membership.py .....................................                                                                                                                                                                                                          [ 83%]
tests\test_metrics.py ...............                                                                                                                                                                                                                                   [ 91%]
tests\test_tsk.py ...............                                                                                                                                                                                                                                       [100%]

============================================================================================================================ 187 passed in 4.65s =============================================================================================================================
PS C:\scted-verify\pr44>
(.venv) cls
PS C:\scted-verify\pr44>
(.venv) python -m pytest tests/ --collect-only -q -o addopts="" | Select-Object -Last 2
Select-String -Path docs\numerical-claims.md -Pattern "Full test-suite size"

python -m pytest tests/test_channel_viability.py -v

187 tests collected in 0.06s

docs\numerical-claims.md:82:| NC-021 | Full test-suite size | 187 | `python -m pytest tests/ --collect-only -q -o addopts=""` (tail line), run on `feature/mert-issue-35-consequent-degeneracy` at `571ffbc` for Issue #35 | 2026-08-28 | Was `166` at `1873625` · +21 from th
is PR (`tests/test_channel_viability.py`, new) · see Rule 6 · cite this row in verification runbooks rather than recalling a count, and state the commit it was measured at · restamp with the merge commit once this branch lands |
============================================================================================================================ test session starts =============================================================================================================================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0 -- C:\scted-verify\pr44\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\scted-verify\pr44
configfile: pyproject.toml
plugins: cov-7.1.0
collected 21 items

tests/test_channel_viability.py::test_is_identity_damping_truth_table[params0-True] PASSED                                                                                                                                                                              [  4%]
tests/test_channel_viability.py::test_is_identity_damping_truth_table[params1-False] PASSED                                                                                                                                                                             [  9%]
tests/test_channel_viability.py::test_is_identity_damping_truth_table[params2-False] PASSED                                                                                                                                                                             [ 14%]
tests/test_channel_viability.py::test_is_identity_damping_truth_table[params3-False] PASSED                                                                                                                                                                             [ 19%]
tests/test_channel_viability.py::test_is_identity_damping_truth_table[params4-True] PASSED                                                                                                                                                                              [ 23%]
tests/test_channel_viability.py::test_is_identity_damping_truth_table[params5-False] PASSED                                                                                                                                                                             [ 28%]
tests/test_channel_viability.py::test_is_identity_damping_rejects_short_vectors PASSED                                                                                                                                                                                  [ 33%]
tests/test_channel_viability.py::test_degenerate_params_project_to_the_identity_channel PASSED                                                                                                                                                                          [ 38%]
tests/test_channel_viability.py::test_zeros_init_is_degenerate PASSED                                                                                                                                                                                                   [ 42%]
tests/test_channel_viability.py::test_is_degenerate_agrees_with_both_entries_zero PASSED                                                                                                                                                                                [ 47%]
tests/test_channel_viability.py::test_first_viable_seed_is_deterministic PASSED                                                                                                                                                                                         [ 52%]
tests/test_channel_viability.py::test_first_viable_seed_returns_the_lowest_viable_seed PASSED                                                                                                                                                                           [ 57%]
tests/test_channel_viability.py::test_first_viable_seed_rejects_nonpositive_limit PASSED                                                                                                                                                                                [ 61%]
tests/test_channel_viability.py::test_first_viable_seed_reports_structural_degeneracy PASSED                                                                                                                                                                            [ 66%]
tests/test_channel_viability.py::test_first_viable_seed_rejects_empty_ensemble PASSED                                                                                                                                                                                   [ 71%]
tests/test_channel_viability.py::test_default_seed_search_limit_is_generous PASSED                                                                                                                                                                                      [ 76%]
tests/test_channel_viability.py::test_degeneracy_rate_is_one_quarter[2-inputs0-12345] PASSED                                                                                                                                                                            [ 80%]
tests/test_channel_viability.py::test_degeneracy_rate_is_one_quarter[3-inputs1-12345] PASSED                                                                                                                                                                            [ 85%]
tests/test_channel_viability.py::test_degeneracy_rate_is_one_quarter[4-inputs2-12345] PASSED                                                                                                                                                                            [ 90%]
tests/test_channel_viability.py::test_degeneracy_rate_is_one_quarter[3-inputs3-999] PASSED                                                                                                                                                                              [ 95%]
tests/test_channel_viability.py::test_first_viable_seed_includes_caller_context PASSED                                                                                                                                                                                  [100%]

============================================================================================================================= 21 passed in 2.98s =============================================================================================================================


PS C:\scted-verify\pr44>
(.venv) python -c "import numpy as np; from qiskit.quantum_info import Kraus, SuperOp; from superconducted.channels.kraus import KrausChannelProjector, NoOpNormalization; p=KrausChannelProjector(NoOpNormalization()); I=SuperOp(Kraus([np.eye(2)])); d=SuperOp(p.project(np.array([0.,0.]),'x',(0,)).to_quantumchannel()); L=SuperOp(p.project(np.array([0.2,0.1]),'x',(0,)).to_quantumchannel()); print('gamma=lambda=0 is identity:', d==I, '| max|diff|:', np.abs(d.data-I.data).max()); print('gamma=0.2, lambda=0.1 is identity:', L==I)"
gamma=lambda=0 is identity: True | max|diff|: 0.0
gamma=0.2, lambda=0.1 is identity: False
PS C:\scted-verify\pr44>
(.venv) python -c "from scripts.first_ensemble_run import _ensemble_for_seed, _synthetic_snapshot; s=_synthetic_snapshot(); [print(p, sum(_ensemble_for_seed(s,1,p,i)[0].is_degenerate for i in range(2000))/2000) for p in ('endpoint','interior')]"
endpoint 0.242
interior 0.242
PS C:\scted-verify\pr44>
(.venv) python -m pytest "tests/test_channel_viability.py::test_degeneracy_rate_is_one_quarter" -v
============================================================================================================================ test session starts =============================================================================================================================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0 -- C:\scted-verify\pr44\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\scted-verify\pr44
configfile: pyproject.toml
plugins: cov-7.1.0
collected 4 items

tests/test_channel_viability.py::test_degeneracy_rate_is_one_quarter[2-inputs0-12345] PASSED                                                                                                                                                                            [ 25%]
tests/test_channel_viability.py::test_degeneracy_rate_is_one_quarter[3-inputs1-12345] PASSED                                                                                                                                                                            [ 50%]
tests/test_channel_viability.py::test_degeneracy_rate_is_one_quarter[4-inputs2-12345] PASSED                                                                                                                                                                            [ 75%]
tests/test_channel_viability.py::test_degeneracy_rate_is_one_quarter[3-inputs3-999] PASSED                                                                                                                                                                              [100%]

============================================================================================================================= 4 passed in 2.96s ==============================================================================================================================
PS C:\scted-verify\pr44>
(.venv) python -c "import io; p='src/superconducted/integration/aer_factory.py'; s=io.open(p,encoding='utf-8').read(); assert 'params.flat[:2] > 0.0' in s; s=s.replace('params.flat[:2] > 0.0','params.flat[:2] >= 0.0'); io.open(p,'w',encoding='utf-8',newline='\n').write(s)"
python -m pytest tests/test_channel_viability.py -q

============================================================================================================================ test session starts =============================================================================================================================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\scted-verify\pr44
configfile: pyproject.toml
plugins: cov-7.1.0
collected 21 items

tests\test_channel_viability.py F...F...FF...F..FFFFF                                                                                                                                                                                                                   [100%]

================================================================================================================================== FAILURES ==================================================================================================================================
_____________________________________________________________________________________________________________ test_is_identity_damping_truth_table[params0-True] _____________________________________________________________________________________________________________

params = [0.0, 0.0], expected = True

    @pytest.mark.parametrize(
        ("params", "expected"),
        [
            ([0.0, 0.0], True),
            ([0.3, 0.0], False),
            ([0.0, 0.3], False),
            ([0.3, 0.3], False),
            # Entries past the first two are the projector's business, not ours.
            ([0.0, 0.0, 0.9], True),
            ([0.9, 0.0, 0.0], False),
        ],
    )
    def test_is_identity_damping_truth_table(params: list[float], expected: bool) -> None:
>       assert is_identity_damping(np.asarray(params, dtype=np.float64)) is expected
E       AssertionError: assert False is True
E        +  where False = is_identity_damping(array([0., 0.]))
E        +    where array([0., 0.]) = <built-in function asarray>([0.0, 0.0], dtype=<class 'numpy.float64'>)
E        +      where <built-in function asarray> = np.asarray
E        +      and   <class 'numpy.float64'> = np.float64

tests\test_channel_viability.py:92: AssertionError
_____________________________________________________________________________________________________________ test_is_identity_damping_truth_table[params4-True] _____________________________________________________________________________________________________________

params = [0.0, 0.0, 0.9], expected = True

    @pytest.mark.parametrize(
        ("params", "expected"),
        [
            ([0.0, 0.0], True),
            ([0.3, 0.0], False),
            ([0.0, 0.3], False),
            ([0.3, 0.3], False),
            # Entries past the first two are the projector's business, not ours.
            ([0.0, 0.0, 0.9], True),
            ([0.9, 0.0, 0.0], False),
        ],
    )
    def test_is_identity_damping_truth_table(params: list[float], expected: bool) -> None:
>       assert is_identity_damping(np.asarray(params, dtype=np.float64)) is expected
E       AssertionError: assert False is True
E        +  where False = is_identity_damping(array([0. , 0. , 0.9]))
E        +    where array([0. , 0. , 0.9]) = <built-in function asarray>([0.0, 0.0, 0.9], dtype=<class 'numpy.float64'>)
E        +      where <built-in function asarray> = np.asarray
E        +      and   <class 'numpy.float64'> = np.float64

tests\test_channel_viability.py:92: AssertionError
_______________________________________________________________________________________________________________________ test_zeros_init_is_degenerate ________________________________________________________________________________________________________________________

dummy_snapshot = CalibrationSnapshot(backend='ibm_test', timestamp=datetime.datetime(2026, 5, 7, 12, 0, tzinfo=datetime.timezone.utc), ... {'name': 'readout_error', 'value': 0.012, 'unit': ''}]], 'gates': [], 'general': []}, target=None, configuration=None)

    def test_zeros_init_is_degenerate(dummy_snapshot: CalibrationSnapshot) -> None:
        """The ADR-014 bootstrap default produces a channel that measures nothing."""
        model = _model(dummy_snapshot, seed=None)
        assert model.crisp_params.tolist() == [0.0, 0.0]
>       assert model.is_degenerate is True
E       assert False is True
E        +  where False = <NoiseModel on []>.is_degenerate

tests\test_channel_viability.py:134: AssertionError
______________________________________________________________________________________________________________ test_is_degenerate_agrees_with_both_entries_zero ______________________________________________________________________________________________________________

dummy_snapshot = CalibrationSnapshot(backend='ibm_test', timestamp=datetime.datetime(2026, 5, 7, 12, 0, tzinfo=datetime.timezone.utc), ... {'name': 'readout_error', 'value': 0.012, 'unit': ''}]], 'gates': [], 'general': []}, target=None, configuration=None)

    def test_is_degenerate_agrees_with_both_entries_zero(
        dummy_snapshot: CalibrationSnapshot,
    ) -> None:
        """Under `ProbabilityClip`, "no positive entry" and "both exactly zero" coincide.

        Issue #35 asks whether "first two crisp parameters non-positive" is even
        the right test. For this pipeline it is exact, and this is the check that
        says so: the clip maps every non-positive raw output to exactly 0.0, so
        the two formulations cannot come apart. They *would* come apart under
        `SigmoidSquashing`, which is why the predicate documents its scope.
        """
        for seed in range(60):
            crisp = _model(dummy_snapshot, seed).crisp_params
            both_zero = bool(crisp[0] == 0.0 and crisp[1] == 0.0)
>           assert is_identity_damping(crisp) is both_zero
E           assert False is True
E            +  where False = is_identity_damping(array([0., 0.]))

tests\test_channel_viability.py:151: AssertionError
____________________________________________________________________________________________________________ test_first_viable_seed_reports_structural_degeneracy ____________________________________________________________________________________________________________

dummy_snapshot = CalibrationSnapshot(backend='ibm_test', timestamp=datetime.datetime(2026, 5, 7, 12, 0, tzinfo=datetime.timezone.utc), ... {'name': 'readout_error', 'value': 0.012, 'unit': ''}]], 'gates': [], 'general': []}, target=None, configuration=None)

    def test_first_viable_seed_reports_structural_degeneracy(
        dummy_snapshot: CalibrationSnapshot,
    ) -> None:
        """Exhausting the search means a structural fault, not a run of bad luck."""
>       with pytest.raises(ValueError, match="not an unlucky run"):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE <class 'ValueError'>

tests\test_channel_viability.py:191: Failed
____________________________________________________________________________________________________________ test_degeneracy_rate_is_one_quarter[2-inputs0-12345] ____________________________________________________________________________________________________________

k_per_input = 2, inputs = [0.5, 0.5, 0.5], rng_seed = 12345

    @pytest.mark.parametrize(
        ("k_per_input", "inputs", "rng_seed"),
        [
            (2, [0.5, 0.5, 0.5], 12345),  # 8 rules - the pre-Issue-#31 grid
            (3, [0.5, 0.5, 0.5], 12345),  # 27 rules - the ratified ADR-010 grid
            (4, [0.5, 0.5, 0.5], 12345),  # 64 rules - beyond the baseline
            (3, [0.01, 0.99, 0.5], 999),  # ratified grid, lopsided input vector
        ],
    )
    def test_degeneracy_rate_is_one_quarter(
        k_per_input: int, inputs: list[float], rng_seed: int
    ) -> None:
        """P(identity channel) = 1/4, invariant to rule count and input vector.

        Issue #35 reported "one draw in four to one in eight" and attributed the
        spread to rule count and input vector. That spread was an eight-sample
        artifact. Rows 0 and 1 of every consequent matrix are disjoint draws from
        the same zero-mean Gaussian, and weighted-average defuzzification is a
        fixed non-negative linear functional of them, so the two crisp outputs
        are i.i.d. zero-mean. Rule count and input vector move their *variance*,
        never their sign, so the rate cannot move either.

        The RNG seed is fixed, so this is deterministic, not flaky. The band is
        roughly +/- 4 standard errors at n = 2000 (s.e. ~= 0.0097) - wide enough
        never to trip on its own, narrow enough to fail loudly if someone makes
        the initialization positive-biased (rate -> 0) or drops the clip.
        """
        rate = _degeneracy_rate(k_per_input, inputs, n_draws=2000, seed=rng_seed)
>       assert 0.21 <= rate <= 0.29, f"expected ~0.25, measured {rate}"
E       AssertionError: expected ~0.25, measured 0.0
E       assert 0.21 <= 0.0

tests\test_channel_viability.py:268: AssertionError
____________________________________________________________________________________________________________ test_degeneracy_rate_is_one_quarter[3-inputs1-12345] ____________________________________________________________________________________________________________

k_per_input = 3, inputs = [0.5, 0.5, 0.5], rng_seed = 12345

    @pytest.mark.parametrize(
        ("k_per_input", "inputs", "rng_seed"),
        [
            (2, [0.5, 0.5, 0.5], 12345),  # 8 rules - the pre-Issue-#31 grid
            (3, [0.5, 0.5, 0.5], 12345),  # 27 rules - the ratified ADR-010 grid
            (4, [0.5, 0.5, 0.5], 12345),  # 64 rules - beyond the baseline
            (3, [0.01, 0.99, 0.5], 999),  # ratified grid, lopsided input vector
        ],
    )
    def test_degeneracy_rate_is_one_quarter(
        k_per_input: int, inputs: list[float], rng_seed: int
    ) -> None:
        """P(identity channel) = 1/4, invariant to rule count and input vector.

        Issue #35 reported "one draw in four to one in eight" and attributed the
        spread to rule count and input vector. That spread was an eight-sample
        artifact. Rows 0 and 1 of every consequent matrix are disjoint draws from
        the same zero-mean Gaussian, and weighted-average defuzzification is a
        fixed non-negative linear functional of them, so the two crisp outputs
        are i.i.d. zero-mean. Rule count and input vector move their *variance*,
        never their sign, so the rate cannot move either.

        The RNG seed is fixed, so this is deterministic, not flaky. The band is
        roughly +/- 4 standard errors at n = 2000 (s.e. ~= 0.0097) - wide enough
        never to trip on its own, narrow enough to fail loudly if someone makes
        the initialization positive-biased (rate -> 0) or drops the clip.
        """
        rate = _degeneracy_rate(k_per_input, inputs, n_draws=2000, seed=rng_seed)
>       assert 0.21 <= rate <= 0.29, f"expected ~0.25, measured {rate}"
E       AssertionError: expected ~0.25, measured 0.0
E       assert 0.21 <= 0.0

tests\test_channel_viability.py:268: AssertionError
____________________________________________________________________________________________________________ test_degeneracy_rate_is_one_quarter[4-inputs2-12345] ____________________________________________________________________________________________________________

k_per_input = 4, inputs = [0.5, 0.5, 0.5], rng_seed = 12345

    @pytest.mark.parametrize(
        ("k_per_input", "inputs", "rng_seed"),
        [
            (2, [0.5, 0.5, 0.5], 12345),  # 8 rules - the pre-Issue-#31 grid
            (3, [0.5, 0.5, 0.5], 12345),  # 27 rules - the ratified ADR-010 grid
            (4, [0.5, 0.5, 0.5], 12345),  # 64 rules - beyond the baseline
            (3, [0.01, 0.99, 0.5], 999),  # ratified grid, lopsided input vector
        ],
    )
    def test_degeneracy_rate_is_one_quarter(
        k_per_input: int, inputs: list[float], rng_seed: int
    ) -> None:
        """P(identity channel) = 1/4, invariant to rule count and input vector.

        Issue #35 reported "one draw in four to one in eight" and attributed the
        spread to rule count and input vector. That spread was an eight-sample
        artifact. Rows 0 and 1 of every consequent matrix are disjoint draws from
        the same zero-mean Gaussian, and weighted-average defuzzification is a
        fixed non-negative linear functional of them, so the two crisp outputs
        are i.i.d. zero-mean. Rule count and input vector move their *variance*,
        never their sign, so the rate cannot move either.

        The RNG seed is fixed, so this is deterministic, not flaky. The band is
        roughly +/- 4 standard errors at n = 2000 (s.e. ~= 0.0097) - wide enough
        never to trip on its own, narrow enough to fail loudly if someone makes
        the initialization positive-biased (rate -> 0) or drops the clip.
        """
        rate = _degeneracy_rate(k_per_input, inputs, n_draws=2000, seed=rng_seed)
>       assert 0.21 <= rate <= 0.29, f"expected ~0.25, measured {rate}"
E       AssertionError: expected ~0.25, measured 0.0
E       assert 0.21 <= 0.0

tests\test_channel_viability.py:268: AssertionError
_____________________________________________________________________________________________________________ test_degeneracy_rate_is_one_quarter[3-inputs3-999] _____________________________________________________________________________________________________________

k_per_input = 3, inputs = [0.01, 0.99, 0.5], rng_seed = 999

    @pytest.mark.parametrize(
        ("k_per_input", "inputs", "rng_seed"),
        [
            (2, [0.5, 0.5, 0.5], 12345),  # 8 rules - the pre-Issue-#31 grid
            (3, [0.5, 0.5, 0.5], 12345),  # 27 rules - the ratified ADR-010 grid
            (4, [0.5, 0.5, 0.5], 12345),  # 64 rules - beyond the baseline
            (3, [0.01, 0.99, 0.5], 999),  # ratified grid, lopsided input vector
        ],
    )
    def test_degeneracy_rate_is_one_quarter(
        k_per_input: int, inputs: list[float], rng_seed: int
    ) -> None:
        """P(identity channel) = 1/4, invariant to rule count and input vector.

        Issue #35 reported "one draw in four to one in eight" and attributed the
        spread to rule count and input vector. That spread was an eight-sample
        artifact. Rows 0 and 1 of every consequent matrix are disjoint draws from
        the same zero-mean Gaussian, and weighted-average defuzzification is a
        fixed non-negative linear functional of them, so the two crisp outputs
        are i.i.d. zero-mean. Rule count and input vector move their *variance*,
        never their sign, so the rate cannot move either.

        The RNG seed is fixed, so this is deterministic, not flaky. The band is
        roughly +/- 4 standard errors at n = 2000 (s.e. ~= 0.0097) - wide enough
        never to trip on its own, narrow enough to fail loudly if someone makes
        the initialization positive-biased (rate -> 0) or drops the clip.
        """
        rate = _degeneracy_rate(k_per_input, inputs, n_draws=2000, seed=rng_seed)
>       assert 0.21 <= rate <= 0.29, f"expected ~0.25, measured {rate}"
E       AssertionError: expected ~0.25, measured 0.0
E       assert 0.21 <= 0.0

tests\test_channel_viability.py:268: AssertionError
_______________________________________________________________________________________________________________ test_first_viable_seed_includes_caller_context _______________________________________________________________________________________________________________

dummy_snapshot = CalibrationSnapshot(backend='ibm_test', timestamp=datetime.datetime(2026, 5, 7, 12, 0, tzinfo=datetime.timezone.utc), ... {'name': 'readout_error', 'value': 0.012, 'unit': ''}]], 'gates': [], 'general': []}, target=None, configuration=None)

    def test_first_viable_seed_includes_caller_context(
        dummy_snapshot: CalibrationSnapshot,
    ) -> None:
        """Callers describe the grid; the search cannot, since `build` is opaque.

        Without this the smoke script had to re-raise and match on message text
        to tell "structural degeneracy" apart from "bad seed_limit".
        """
>       with pytest.raises(ValueError, match="27 rules"):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE <class 'ValueError'>

tests\test_channel_viability.py:279: Failed
========================================================================================================================== short test summary info ===========================================================================================================================
FAILED tests/test_channel_viability.py::test_is_identity_damping_truth_table[params0-True] - AssertionError: assert False is True
FAILED tests/test_channel_viability.py::test_is_identity_damping_truth_table[params4-True] - AssertionError: assert False is True
FAILED tests/test_channel_viability.py::test_zeros_init_is_degenerate - assert False is True
FAILED tests/test_channel_viability.py::test_is_degenerate_agrees_with_both_entries_zero - assert False is True
FAILED tests/test_channel_viability.py::test_first_viable_seed_reports_structural_degeneracy - Failed: DID NOT RAISE <class 'ValueError'>
FAILED tests/test_channel_viability.py::test_degeneracy_rate_is_one_quarter[2-inputs0-12345] - AssertionError: expected ~0.25, measured 0.0
FAILED tests/test_channel_viability.py::test_degeneracy_rate_is_one_quarter[3-inputs1-12345] - AssertionError: expected ~0.25, measured 0.0
FAILED tests/test_channel_viability.py::test_degeneracy_rate_is_one_quarter[4-inputs2-12345] - AssertionError: expected ~0.25, measured 0.0
FAILED tests/test_channel_viability.py::test_degeneracy_rate_is_one_quarter[3-inputs3-999] - AssertionError: expected ~0.25, measured 0.0
FAILED tests/test_channel_viability.py::test_first_viable_seed_includes_caller_context - Failed: DID NOT RAISE <class 'ValueError'>
======================================================================================================================= 10 failed, 11 passed in 3.64s ========================================================================================================================
PS C:\scted-verify\pr44>
(.venv) git checkout -- src/superconducted/integration/aer_factory.py
git status --short
python -m pytest tests/test_channel_viability.py -q


============================================================================================================================ test session starts =============================================================================================================================
platform win32 -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\scted-verify\pr44
configfile: pyproject.toml
plugins: cov-7.1.0
collected 21 items

tests\test_channel_viability.py .....................                                                                                                                                                                                                                   [100%]

============================================================================================================================= 21 passed in 2.99s =============================================================================================================================
PS C:\scted-verify\pr44>
(.venv) python scripts/first_ensemble_run.py --qubits 2 --mf-placement endpoint
python scripts/first_ensemble_run.py --qubits 2 --mf-placement interior
--- Ensemble Scaling Tests (Real Concretes) ---
  [n=1] mf_placement=endpoint consequent_seed=1
N=1 elapsed=0.09s members=1 shots_per_member=1024
  counts: {'00': 244, '10': 244, '01': 277, '11': 259}

  [n=8] mf_placement=endpoint consequent_seed=1
N=8 elapsed=0.92s members=8 shots_per_member=1024
  counts: {'00': 270, '10': 255, '11': 252, '01': 247}

  [n=16] mf_placement=endpoint consequent_seed=1
N=16 elapsed=1.85s members=16 shots_per_member=1024
  counts: {'01': 258, '11': 254, '00': 256, '10': 256}

--- Sanity Check (Single Member, 8192 Shots) ---
Sanity Run elapsed=0.14s total_shots=8192
  counts: {'01': 2004, '11': 2072, '00': 2051, '10': 2065}
--- Ensemble Scaling Tests (Real Concretes) ---
  [n=1] mf_placement=interior consequent_seed=0
N=1 elapsed=0.09s members=1 shots_per_member=1024
  counts: {'10': 256, '00': 263, '01': 249, '11': 256}

  [n=8] mf_placement=interior consequent_seed=0
N=8 elapsed=0.93s members=8 shots_per_member=1024
  counts: {'01': 252, '11': 258, '00': 257, '10': 258}

  [n=16] mf_placement=interior consequent_seed=0
N=16 elapsed=1.87s members=16 shots_per_member=1024
  counts: {'00': 252, '10': 257, '11': 260, '01': 255}

--- Sanity Check (Single Member, 8192 Shots) ---
Sanity Run elapsed=0.14s total_shots=8192
  counts: {'11': 2074, '10': 1955, '00': 2147, '01': 2016}
PS C:\scted-verify\pr44>
(.venv) python -c "from scripts.first_ensemble_run import FEATURE_SCALES, _default_mfs_for_feature; from superconducted.fuzzy.tsk import TSKRuleBase; print('n_rules =', TSKRuleBase.from_grid(per_input_mfs=[_default_mfs_for_feature(n) for n in FEATURE_SCALES], output_dim=2).n_rules)"
n_rules = 27
PS C:\scted-verify\pr44>
(.venv) Stop-Transcript
**********************
Windows PowerShell transcript end
End time: 20260831020645
**********************

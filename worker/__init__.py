"""Valora3D cloud render worker (RunPod serverless): one job = fetch a GLB, run `engine.site_job`, encode, upload.

The engine is a black box behind the `py -m engine.site_job run` CLI and its `SITEJOB {json}` progress lines;
nothing here imports `engine`. See worker/README.md for the job contract and deployment."""

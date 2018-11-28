# Usage

Install the dependencies, run

```bash
export FLASK_APP=${BGPRANKING_HOME}/website/web/__init__.py
gunicorn --worker-class gevent -w 10 -b 0.0.0.0:5005 web:app
```


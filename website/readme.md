# Usage

Install the dependencies, run

```bash
export FLASK_APP=${BGPRANKING_HOME}/website/web/__init__.py
gunicorn --worker-class gevent -w 10 -b 127.0.0.1:5005 web:app
```


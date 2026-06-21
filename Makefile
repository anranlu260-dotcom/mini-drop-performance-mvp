.PHONY: test coverage demo run package clean

test:
	python3 -m unittest discover -s tests -v

coverage:
	python3 coverage_check.py

run:
	python3 server.py --host 127.0.0.1 --port 8080

demo:
	python3 demo.py --server http://127.0.0.1:8080

continuous-demo:
	python3 continuous_demo.py --server http://127.0.0.1:8080 --pid 1

package:
	python3 package.py

clean:
	rm -f data/*.sqlite3 data/*.sqlite3-shm data/*.sqlite3-wal

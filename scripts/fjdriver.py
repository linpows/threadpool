#!/usr/bin/python

#
# fjdriver.py for Fork/Join pool projects
#
# Written by Godmar Back and Scott Pruett
# first version created Fall 2014, CS 3214
#
# https://git-scm.com/docs/pretty-formats
version = "$Format:%H committed by %cn$"

#
import getopt, sys, os, subprocess, signal, re, json, resource, time, socket
from datetime import datetime
from collections import namedtuple, defaultdict

# add location of this script to python sys.path
# add directory in which script is located to python path
script_dir = "/".join(__file__.split("/")[:-1])
if script_dir == "":
    script_dir = "."

script_dir = os.path.realpath(script_dir)
if script_dir not in sys.path:
    sys.path.append(script_dir)

from fjtests import load_test_module

src_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__))) + "/tests"
results_file = "full-results.json"
filelist = src_dir + "/FILELIST"
timestamp = str(datetime.now()).replace(" ", "_")
workdir = "fj_testdir_" + timestamp
poolfile = "./threadpool.c"
verbose = False
silent = False
list_tests = False
large_tests = False
grade_mode = False
benchmark_runs = 1
large_node = False

large_amd_nodes = ['fir.rlogin', 'sourwood.rlogin']
if socket.gethostname() in large_amd_nodes:
    large_node = True

# Benchmark info

# Times of serial runs for benchmarked tests
benchmark_times = {
    'nqueens 13':      38.82948,
    'quicksort large': 19.81442,
    'mergesort large': 22.33417
}

tests = load_test_module('standard')

#
# getopt
#
# look for threadpool.c in current dir, or point at with flag
#
def usage():
    print """
Usage: %s [options]
    -v              Verbose
    -V              Print Version and exit
    -a              Run benchmark anyway even if machine is not idle
    -r              Only run required tests.
    -h              Show help 
    -p              <file> - Location of threadpool implementation, default ./threadpool.c
    -l              List available tests
    -t              Filter test by name, given as a comma separated list.
                    e.g.: -t basic1,psum
    -L              Run large benchmarked tests, specific to which rlogin
                    node you are on
    -B              Provide number of runs. The output will be average of all the runs
                    e.g. : -B 5
    -F              Location of file from varsys TODO
    -S              Test size : small, medium or large. Coupled with -F only (varsys)
    -T              Number of threads for running the test. Coupled with -F only (varsys)
    Varsys usage example:
    python fjdriver.py -g -t quicksort -F <folder location> -S <size> -T <threadcount>

    """ % (sys.argv[0])

try:
    opts, args = getopt.getopt(sys.argv[1:], "Varvhlp:F:S:T:t:o:B:gL", ["verbose", "help", "list-tests"])
except getopt.GetoptError, err:
    print str(err) # will print something like "option -a not recognized"
    usage()
    sys.exit(2)

runfilter = lambda test : True
ignore_if_not_idle = False
from_varsys = False
test_size = "small"
for opt, arg in opts: 
    if opt == "-r":
        oldrunfilter = runfilter
        runfilter = lambda test: test.is_required and oldrunfilter(test)

    elif opt == "-V":
        print "Version", version
        sys.exit(0)
    elif opt == "-a":
        ignore_if_not_idle = True
    elif opt == "-v":
        verbose = True
    elif opt in ("-h", "--help"):
        usage()
        sys.exit()
    elif opt == '-p':
        poolfile = arg
    elif opt == '-l':
        list_tests = True
    elif opt == '-o':
        results_file = arg
    elif opt == '-B':
        benchmark_runs = int(arg)
    elif opt == '-F':
        from_varsys =  True
        dir_path = arg   # file from argument
        if os.path.isdir(dir_path) is False :
            print 'Given directory doesn\'t exist : %s' % dir_path
            sys.exit() 
        src_dir = dir_path
        results_file = "full-results.json"
        filelist = src_dir + "/FILELIST"
        workdir = src_dir
    elif opt == '-S':
        if arg in ["small", "medium", "large"] :
            test_size = arg
        else :
            print 'Given size should be small/medium/large : %s ' % arg
            sys.exit() 
    elif opt == '-T':
        threads = int(arg)
    elif opt == '-g':
        grade_mode = True
    elif opt == '-L':
        large_tests = True
        tests = load_test_module('large')
    elif opt == '-t':
        filtered = arg.split(',')
        for filter in filtered:
            for test in tests:
                if filter == test.name:
                    break
            else:
                print 'Unknown test: %s. Use -l to list test names.' % filter
                usage()
                sys.exit()
        oldrunfilter = runfilter
        runfilter = lambda test: test.name in filtered and oldrunfilter(test)
    else:
        assert False, "unhandled option"

if large_node and not large_tests:
    print 'Please only use large rlogin nodes (fir, sourwood) for benchmarking.'
    print 'Use the -L switch if you intend to benchmark on this node.'
    sys.exit()


if list_tests:
    print 'Available tests (with applied filters):'
    print 80 * '='
    for test in tests:
        if runfilter(test):
            print '%s: %s' % (test.name, test.description)
    sys.exit()

def copyfile(src, dst):
    cmd = "cp %s %s" % (src, dst)
    if verbose:
        print cmd
    ex = os.system(cmd)
    if ex:
        sys.exit(ex)

def setup_working_directory():
    if from_varsys :
        print "Working from varsys provided dir",  workdir
    else :
        if verbose:
            print "Creating working directory",  workdir

        os.mkdir(workdir)

        if verbose:
            print "Copying files"

        if not os.access(poolfile, os.R_OK):
            print
            print "I cannot find %s" % poolfile
            usage()
            sys.exit(2)

        copyfile(poolfile, workdir + "/threadpool.c")

        flist = open(filelist, 'r')
        for file in flist:
            if file.startswith("#"):
                continue
            file = file.strip()
            copyfile(src_dir + "/" + file, workdir)

        flist.close()
        if verbose:
            print "Copying %s" % poolfile


    print workdir
    os.chdir(workdir)

    if os.system("make"):
        if grade_mode:
            op = open(results_file, 'w')
            op.write(json.dumps({'error': 'did not compile'}))
            op.close()
        raise Exception("make failed, run 'make' in %s to see why" % workdir)

def check_software_engineering(objfile, allowedsymbols):
    hex = "[0-9A-Fa-f]{8,16}"
    if verbose:
        print "Performing some checks that %s conforms to accepted software engineering practice..." % objfile

    symbols = subprocess.Popen(["nm", objfile], stdout=subprocess.PIPE)\
        .communicate()[0].split("\n")

    for sym in symbols:
        if sym == "" or re.match("\s+U (\S+)", sym):
            continue

        m = re.match(hex + " (\S) (\S+)", sym)
        if not m:
            raise Exception("unexpected line in nm:\n" + sym)

        if m.group(1).islower():    # local symbols are fine
            continue

        if m.group(1) == "T":
            if m.group(2) in allowedsymbols:
                continue
            
            if grade_mode:
                op = open(results_file, 'w')
                op.write(json.dumps({'error': 'defines global function %s' % m.group(2)}))
                op.close()
            raise Exception(("%s defines global function '%s'\n"
                +"allowed functions are: %s") % (objfile, m.group(2), str(allowedsymbols)))

        if grade_mode:
            op = open(results_file, 'w')
            op.write(json.dumps({'error': 'defines global symbol %s' % m.group(2)}))
            op.close()
        raise Exception(("%s must not define any global or static variables"
                +", but you define: %s") % (objfile, m.group(2)))

allowedsymbols = [ "future_free", "future_get",
                   "thread_pool_new", "thread_pool_shutdown_and_destroy", 
                   "thread_pool_submit" ] 

#
# build it (like check.py)
#

def count_number_of_processes():
    proc = subprocess.Popen(["ps", "ux"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    stdout, stderr = proc.communicate()
    # -2 for ps and header
    return len(stdout.strip().split('\n')) - 2

def get_load_average():
    """
    Returns tuple nproc, loadavg where nproc is the current number of
    running threads (minus 1) and loadavg is the load average
    """
    # 0.57 0.65 0.54 1/426 28121
    f = open("/proc/loadavg")
    c = f.read().strip()
    m = re.match(r'(\S+) \S+ \S+ (\d+)/\d+ \d+', c)
    load = float(m.groups()[0])
    nprocs = int(m.groups()[1])
    f.close()
    return nprocs - 1, load

def wait_for_load_to_go_down():
    while True:
        nprocs, load = get_load_average()
        if nprocs == 0 and load < 1.0:
            break

        print "Warning. There are other %d processes running on this machine, loadavg %f." % (nprocs, load)
        print "Sleeping for 1 second.  Use the -a switch to run the benchmarks regardless."
        time.sleep(1.0)

# run tests
#
# echo test:
#  progname  + set of inputs/cmdline parameters
#
# each should support -n <thread> for number of threads
#

#
# result: expected output + exit code(?)
#

def set_threadlimit(nthreads):
    def closure():
        resource.setrlimit(resource.RLIMIT_NPROC, (nthreads, nthreads))
    return closure

def run_single_test(test, run, threads):
    cmdline = ['timeout', str(run.timeout), test.command, '-n', str(threads)] + run.args
    rundata = {
        'command' : ' '.join(cmdline),
        'nthreads' : threads
    }
    def addrundata(d):
        for k, v in d.items():
            rundata[k] = v

    if not silent:
        print 'Running:', ' '.join(cmdline),
        sys.stdout.flush()
    infile = None
    if run.input_file:
        infile = open(run.input_file, 'r')
    # preexec_fn sets the system-wide NPROC for this user.
    # we set it to #threads + 1 (for the main thread)
    # plus existing procs
    starttime = time.time()
    proc = subprocess.Popen(cmdline, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, stdin=infile,
                            preexec_fn=set_threadlimit(threads + 2 + number_of_existing_processes))

    stdout, stderr = proc.communicate()
    if grade_mode:
        stdout = stdout[:100]
        stderr = stderr[:100]
    runningtime = time.time() - starttime

    if infile:
        infile.close()

    signames = dict((k, v) for v, k in signal.__dict__.iteritems() if v.startswith('SIG'))
    signum = proc.returncode - 128
    if proc.returncode < 0:
        signum = -proc.returncode
    if proc.returncode >= 128 or proc.returncode < 0 and signum in signames:
        timeoutmsg = ''
        if runningtime >= run.timeout:
            timeoutmsg = '\nProgram ran and most likely timed out at %.3fs' % (runningtime)
        error = """\
        Program terminated with signal %d (%s) %s
        --------------------------------------------
        Program output:
        %s
        StdErr output:
        %s
        """ % (signum, signames[signum], timeoutmsg, stdout, stderr)
        addrundata({
            'error': error
        })
        if not silent:
            print '[ ]'
            if verbose or grade_mode:
                print error

    elif proc.returncode > 0:
        # non-zero exit code
        timeoutmsg = ''
        if proc.returncode == 124:
            timeoutmsg = '\nProgram ran and most likely timed out at %.3fs' % (runningtime)

        error = """\
        Program exited with non-zero exit status %d. %s
        --------------------------------------------
        Program output:
        %s
        StdErr output:
        %s
        """ % (proc.returncode, timeoutmsg, stdout, stderr)

        addrundata({
            'error': error
        })
        if not silent:
            print '[ ]'
            if verbose or grade_mode:
                print error

    else:
        if not silent:
            print '[+]'

        outfile = 'runresult.%d.json' % (proc.pid)
        if not os.access(outfile, os.R_OK):
            addrundata({
                'error': 'The benchmark did not create the expected result file %s' % outfile
            })
        else:
            f = open(outfile, 'r')
            data = f.read()
            f.close()
            addrundata(json.loads(data))
            rundata['stdout'] = stdout
            if len(stderr) > 0: 
                rundata['stderr'] = stderr
            os.unlink(outfile)
    return rundata
    
def average_run(runs):
    data = {
        'nthreads': runs[0]['nthreads'],
        'command': runs[0]['command']
    }
    totalrtime = 0.0
    totalstime = 0.0
    totalutime = 0.0
    error = None
    passed = 0
    for run in runs:
        if 'error' in run:
            error = run['error']
        else:
            passed += 1
            totalrtime += run['realtime']
            totalstime += run['ru_stime']
            totalutime += run['ru_utime']

    if error or passed != len(runs):
        data['error'] = error
        data['run_count'] = len(runs)
        data['passed'] = passed
    else:
        data['realtime'] = totalrtime / len(runs)
        data['cputime'] = (totalstime + totalutime) / len(runs)
        data['ru_stime'] = totalstime / len(runs)
        data['ru_utime'] = totalutime / len(runs)
        data['run_count'] = len(runs)
        data['passed'] = passed

    return data

def benchmark_speedup(data, testname):
    if 'realtime' not in data or 'cputime' not in data:
        return
    serial_time = benchmark_times[testname]
    data['speedup'] = serial_time / data['realtime']
    data['cpu_overuse'] = data['cputime'] / data['realtime']

def run_tests(tests):
    results = defaultdict(dict)

    summary = {}
    for test in tests:
        if not runfilter(test):
            if verbose:
                print 'Skipping test: ' + test.description
            continue

        if not silent:
            print ''
            print 'Starting test: ' + test.description
            print '=' * 80

        results[test.name] = {}
        for run in test.runs:
            perthreadresults = []
            results[test.name][run.name] = perthreadresults

            for threads in run.thread_count:
                if grade_mode:
                    repeats = benchmark_runs if test.is_required or run.is_benchmarked else 1
                    runs = []
                    for repeat in range(repeats):
                        runs.append(run_single_test(test, run, threads))
                    rundata = average_run(runs)
                    rundata['runs'] = runs
                    if run.is_benchmarked:
                        benchmark_speedup(rundata, run.name)
                    perthreadresults.append(rundata)
                else:
                    runs = [run_single_test(test, run, threads)]
                    rundata = average_run(runs)
                    rundata['runs'] = runs
                    perthreadresults.append(rundata)
    return results


def run_tests_varsys(tests, test_size):
    results = defaultdict(dict)

    summary = {}
    for test in tests:
        if not runfilter(test):
            if verbose:
                print 'Skipping test: ' + test.description
            continue

        if not silent:
            print ''
            print 'Starting test: ' + test.description
            print '=' * 80

        results[test.name] = {}
        for run in test.runs:
            if test_size not in run.name :
                continue # skip the test run, only run the specific size
            perthreadresults = []
            results[test.name][run.name] = perthreadresults

            if grade_mode:
                repeats = benchmark_runs
                runs = []
                for repeat in range(repeats):
                    runs.append(run_single_test(test, run, threads))
                rundata = average_run(runs)
                rundata['runs'] = runs
                #benchmark_speedup(rundata, run.name) TODO figure out its work
                perthreadresults.append(rundata)
    return results




def print_results(results):
    print json.dumps(results, indent = 4, sort_keys = True, separators = (',', ': '))

def write_results_to_json(filename):
    jfile = open(results_file, "w")
    print >>jfile, json.dumps(results, indent = 4, sort_keys = True, separators = (',', ': '))
    jfile.close()

def find_thread_run(perthreadresults, threadcount):
    for result in perthreadresults:
        if result['nthreads'] == threadcount:
            return result
    return None

def print_grade_table(results, tests):
    thread_headers =  [1, 2, (4, 5), (8, 10), (16, 20)]
    if large_tests and large_node:
        thread_headers = [8, 16, 32, 64]
    elif large_tests:
        thread_headers = [5, 10, 20]
    print ''
    print 'Test name:' + (16 * ' ') + ''.join(map(lambda x: '%-10s' % str(x), thread_headers))
    print '='*80
    minimum_requirements = True
    for test in tests:
        if not runfilter(test) and test.is_required:
            if not silent:
                print 'WARNING: Skipping minimum requirement test (%s), will not say you passed!' % test.name
            minimum_requirements = False

        if not runfilter(test):
            continue
        if not test.name in results:
            print '%s: could not find test data!' % test.name
        res = results[test.name]
        print '%s:' % test.name.upper() + '  ' + test.description
    
        passed = True
        for run in test.runs:
            statuses = []
            for threads in thread_headers:
                if isinstance(threads, int):
                    thread_run = find_thread_run(res[run.name], threads)
                else:
                    for t in threads:
                        thread_run = find_thread_run(res[run.name], t)
                        if thread_run:
                            break
                if not thread_run:
                    statuses.append('')
                elif 'error' in thread_run:
                    passed = False
                    statuses.append('[ ]')
                elif run.is_benchmarked:
                    statuses.append('[%.3fs]' % thread_run['realtime'])
                else:
                    statuses.append('[X]')

            print '  %-23s' % (run.name) + ''.join(map(lambda x: '%-10s' % x, statuses))
        
        if not passed and test.is_required:
            minimum_requirements = False

    print '='*80
    if minimum_requirements and not large_tests:
        print 'You have met minimum requirements.'
    elif not large_tests:
        print 'You did not meet minimum requirements.'


def print_grade_table_varsys(results, tests):
    for test in tests:
        if not runfilter(test):
            continue
        if not test.name in results:
            print '%s: could not find test data!' % test.name
        res = results[test.name]
        print '%s:' % test.name.upper() + '  ' + test.description
        for run in test.runs:
            if test_size not in run.name :
                continue 
            statuses = []
            thread_run = find_thread_run(res[run.name], threads)
            statuses.append('[%.3fs]' % thread_run['realtime'])
            print '  %-23s' % (run.name) + ''.join(map(lambda x: '%-10s' % x, statuses))

    print '='*80




setup_working_directory()
check_software_engineering("threadpool.o", allowedsymbols)
number_of_existing_processes = count_number_of_processes()
if verbose:
    print "There are %d process currently running for user %s" % (number_of_existing_processes, os.getlogin())

if not ignore_if_not_idle:
    wait_for_load_to_go_down()

if from_varsys is False :
    results = run_tests(tests)
    if verbose:
        print_results(results)
    if not silent:
        print_grade_table(results, tests)

else :
    results = run_tests_varsys(tests, test_size)  #test name will be handled inside
    print_grade_table_varsys(results, tests)

if not large_node:
    write_results_to_json(results_file)
    print "Wrote full results to %s/%s" % (workdir, results_file)


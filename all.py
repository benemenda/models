
#This file: schedules_test.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Tests for common.schedules."""

from math import exp
from math import sqrt
import numpy as np
from six.moves import xrange
import tensorflow as tf

from common import config_lib  # brain coder
from common import schedules  # brain coder


class SchedulesTest(tf.test.TestCase):

  def ScheduleTestHelper(self, config, schedule_subtype, io_values):
    """Run common checks for schedules.

    Args:
      config: Config object which is passed into schedules.make_schedule.
      schedule_subtype: The expected schedule type to be instantiated.
      io_values: List of (input, output) pairs. Must be in ascending input
          order. No duplicate inputs.
    """

    # Check that make_schedule makes the correct type.
    f = schedules.make_schedule(config)
    self.assertTrue(isinstance(f, schedule_subtype))

    # Check that multiple instances returned from make_schedule behave the same.
    fns = [schedules.make_schedule(config) for _ in xrange(3)]

    # Check that all the inputs map to the right outputs.
    for i, o in io_values:
      for f in fns:
        f_out = f(i)
        self.assertTrue(
            np.isclose(o, f_out),
            'Wrong value at input %d. Expected %s, got %s' % (i, o, f_out))

    # Check that a subset of the io_values are still correct.
    f = schedules.make_schedule(config)
    subseq = [io_values[i**2] for i in xrange(int(sqrt(len(io_values))))]
    if subseq[-1] != io_values[-1]:
      subseq.append(io_values[-1])
    for i, o in subseq:
      f_out = f(i)
      self.assertTrue(
          np.isclose(o, f_out),
          'Wrong value at input %d. Expected %s, got %s' % (i, o, f_out))

    # Check duplicate calls.
    f = schedules.make_schedule(config)
    for i, o in io_values:
      for _ in xrange(3):
        f_out = f(i)
        self.assertTrue(
            np.isclose(o, f_out),
            'Duplicate calls at input %d are not equal. Expected %s, got %s'
            % (i, o, f_out))

  def testConstSchedule(self):
    self.ScheduleTestHelper(
        config_lib.Config(fn='const', const=5),
        schedules.ConstSchedule,
        [(0, 5), (1, 5), (10, 5), (20, 5), (100, 5), (1000000, 5)])

  def testLinearDecaySchedule(self):
    self.ScheduleTestHelper(
        config_lib.Config(fn='linear_decay', initial=2, final=0, start_time=10,
                          end_time=20),
        schedules.LinearDecaySchedule,
        [(0, 2), (1, 2), (10, 2), (11, 1.8), (15, 1), (19, 0.2), (20, 0),
         (100000, 0)])

    # Test step function.
    self.ScheduleTestHelper(
        config_lib.Config(fn='linear_decay', initial=2, final=0, start_time=10,
                          end_time=10),
        schedules.LinearDecaySchedule,
        [(0, 2), (1, 2), (10, 2), (11, 0), (15, 0)])

  def testExponentialDecaySchedule(self):
    self.ScheduleTestHelper(
        config_lib.Config(fn='exp_decay', initial=exp(-1), final=exp(-6),
                          start_time=10, end_time=20),
        schedules.ExponentialDecaySchedule,
        [(0, exp(-1)), (1, exp(-1)), (10, exp(-1)), (11, exp(-1/2. - 1)),
         (15, exp(-5/2. - 1)), (19, exp(-9/2. - 1)), (20, exp(-6)),
         (100000, exp(-6))])

    # Test step function.
    self.ScheduleTestHelper(
        config_lib.Config(fn='exp_decay', initial=exp(-1), final=exp(-6),
                          start_time=10, end_time=10),
        schedules.ExponentialDecaySchedule,
        [(0, exp(-1)), (1, exp(-1)), (10, exp(-1)), (11, exp(-6)),
         (15, exp(-6))])

  def testSmootherstepDecaySchedule(self):
    self.ScheduleTestHelper(
        config_lib.Config(fn='smooth_decay', initial=2, final=0, start_time=10,
                          end_time=20),
        schedules.SmootherstepDecaySchedule,
        [(0, 2), (1, 2), (10, 2), (11, 1.98288), (15, 1), (19, 0.01712),
         (20, 0), (100000, 0)])

    # Test step function.
    self.ScheduleTestHelper(
        config_lib.Config(fn='smooth_decay', initial=2, final=0, start_time=10,
                          end_time=10),
        schedules.SmootherstepDecaySchedule,
        [(0, 2), (1, 2), (10, 2), (11, 0), (15, 0)])

  def testHardOscillatorSchedule(self):
    self.ScheduleTestHelper(
        config_lib.Config(fn='hard_osc', high=2, low=0, start_time=100,
                          period=10, transition_fraction=0.5),
        schedules.HardOscillatorSchedule,
        [(0, 2), (1, 2), (10, 2), (100, 2), (101, 1.2), (102, 0.4), (103, 0),
         (104, 0), (105, 0), (106, 0.8), (107, 1.6), (108, 2), (109, 2),
         (110, 2), (111, 1.2), (112, 0.4), (115, 0), (116, 0.8), (119, 2),
         (120, 2), (100001, 1.2), (100002, 0.4), (100005, 0), (100006, 0.8),
         (100010, 2)])

    # Test instantaneous step.
    self.ScheduleTestHelper(
        config_lib.Config(fn='hard_osc', high=2, low=0, start_time=100,
                          period=10, transition_fraction=0),
        schedules.HardOscillatorSchedule,
        [(0, 2), (1, 2), (10, 2), (99, 2), (100, 0), (104, 0), (105, 2),
         (106, 2), (109, 2), (110, 0)])


if __name__ == '__main__':
  tf.test.main()

#This file: bf.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""BrainF**k interpreter.

Language info: https://en.wikipedia.org/wiki/Brainfuck

Based on public implementation:
https://github.com/pocmo/Python-Brainfuck/blob/master/brainfuck.py
"""

from collections import namedtuple
import time


EvalResult = namedtuple(
    'EvalResult', ['output', 'success', 'failure_reason', 'steps', 'time',
                   'memory', 'program_trace'])


ExecutionSnapshot = namedtuple(
    'ExecutionSnapshot',
    ['codeptr', 'codechar', 'memptr', 'memval', 'memory', 'next_input',
     'output_buffer'])


class Status(object):
  SUCCESS = 'success'
  TIMEOUT = 'timeout'
  STEP_LIMIT = 'step-limit'
  SYNTAX_ERROR = 'syntax-error'


CHARS = INT_TO_CHAR = ['>', '<', '+', '-', '[', ']', '.', ',']
CHAR_TO_INT = dict([(c, i) for i, c in enumerate(INT_TO_CHAR)])


class LookAheadIterator(object):
  """Same API as Python iterator, with additional peek method."""

  def __init__(self, iterable):
    self._it = iter(iterable)
    self._current_element = None
    self._done = False
    self._preload_next()

  def _preload_next(self):
    try:
      self._current_element = self._it.next()
    except StopIteration:
      self._done = True

  def next(self):
    if self._done:
      raise StopIteration
    element = self._current_element
    self._preload_next()
    return element

  def peek(self, default_value=None):
    if self._done:
      if default_value is None:
        raise StopIteration
      return default_value
    return self._current_element


def buildbracemap(code):
  """Build jump map.

  Args:
    code: List or string or BF chars.

  Returns:
    bracemap: dict mapping open and close brace positions in the code to their
        destination jumps. Specifically, positions of matching open/close braces
        if they exist.
    correct_syntax: True if all braces match. False if there are unmatched
        braces in the code. Even if there are unmatched braces, a bracemap will
        be built, and unmatched braces will map to themselves.
  """
  bracestack, bracemap = [], {}

  correct_syntax = True
  for position, command in enumerate(code):
    if command == '[':
      bracestack.append(position)
    if command == ']':
      if not bracestack:  # Unmatched closing brace.
        bracemap[position] = position  # Don't jump to any position.
        correct_syntax = False
        continue
      start = bracestack.pop()
      bracemap[start] = position
      bracemap[position] = start
  if bracestack:  # Unmatched opening braces.
    for pos in bracestack:
      bracemap[pos] = pos  # Don't jump to any position.
      correct_syntax = False
  return bracemap, correct_syntax


def evaluate(code, input_buffer=None, init_memory=None, base=256, timeout=1.0,
             max_steps=None, require_correct_syntax=True, output_memory=False,
             debug=False):
  """Execute BF code.

  Args:
    code: String or list of BF characters. Any character not in CHARS will be
        ignored.
    input_buffer: A list of ints which will be used as the program's input
        stream. Each read op "," will read an int from this list. 0's will be
        read once the end of the list is reached, or if no input buffer is
        given.
    init_memory: A list of ints. Memory for first k positions will be
        initialized to this list (where k = len(init_memory)). Memory positions
        are initialized to 0 by default.
    base: Integer base for the memory. When a memory value is incremented to
        `base` it will overflow to 0. When a memory value is decremented to -1
        it will underflow to `base` - 1.
    timeout: Time limit for program execution in seconds. Set to None to
        disable.
    max_steps: Execution step limit. An execution step is the execution of one
        operation (code character), even if that op has been executed before.
        Execution exits when this many steps are reached. Set to None to
        disable. Disabled by default.
    require_correct_syntax: If True, unmatched braces will cause `evaluate` to
        return without executing the code. The failure reason will be
        `Status.SYNTAX_ERROR`. If False, unmatched braces are ignored
        and execution will continue.
    output_memory: If True, the state of the memory at the end of execution is
        returned.
    debug: If True, then a full program trace will be returned.

  Returns:
    EvalResult namedtuple containing
      output: List of ints which were written out by the program with the "."
          operation.
      success: Boolean. Whether execution completed successfully.
      failure_reason: One of the attributes of `Status`. Gives extra info
          about why execution was not successful.
      steps: Number of execution steps the program ran for.
      time: Amount of time in seconds the program ran for.
      memory: If `output_memory` is True, a list of memory cells up to the last
          one written to. otherwise, None.
  """
  input_iter = (
      LookAheadIterator(input_buffer) if input_buffer is not None
      else LookAheadIterator([]))

  # Null memory value. This is the value of an empty memory. Also the value
  # returned by the read operation when the input buffer is empty, or the
  # end of the buffer is reached.
  null_value = 0

  code = list(code)
  bracemap, correct_syntax = buildbracemap(code)  # will modify code list
  if require_correct_syntax and not correct_syntax:
    return EvalResult([], False, Status.SYNTAX_ERROR, 0, 0.0,
                      [] if output_memory else None, [] if debug else None)

  output_buffer = []

  codeptr, cellptr = 0, 0

  cells = list(init_memory) if init_memory else [0]

  program_trace = [] if debug else None
  success = True
  reason = Status.SUCCESS
  start_time = time.time()
  steps = 0
  while codeptr < len(code):
    command = code[codeptr]

    if debug:
      # Add step to program trace.
      program_trace.append(ExecutionSnapshot(
          codeptr=codeptr, codechar=command, memptr=cellptr,
          memval=cells[cellptr], memory=list(cells),
          next_input=input_iter.peek(null_value),
          output_buffer=list(output_buffer)))

    if command == '>':
      cellptr += 1
      if cellptr == len(cells): cells.append(null_value)

    if command == '<':
      cellptr = 0 if cellptr <= 0 else cellptr - 1

    if command == '+':
      cells[cellptr] = cells[cellptr] + 1 if cells[cellptr] < (base - 1) else 0

    if command == '-':
      cells[cellptr] = cells[cellptr] - 1 if cells[cellptr] > 0 else (base - 1)

    if command == '[' and cells[cellptr] == 0: codeptr = bracemap[codeptr]
    if command == ']' and cells[cellptr] != 0: codeptr = bracemap[codeptr]

    if command == '.': output_buffer.append(cells[cellptr])
    if command == ',': cells[cellptr] = next(input_iter, null_value)

    codeptr += 1
    steps += 1

    if timeout is not None and time.time() - start_time > timeout:
      success = False
      reason = Status.TIMEOUT
      break
    if max_steps is not None and steps >= max_steps:
      success = False
      reason = Status.STEP_LIMIT
      break

  if debug:
    # Add step to program trace.
    command = code[codeptr] if codeptr < len(code) else ''
    program_trace.append(ExecutionSnapshot(
        codeptr=codeptr, codechar=command, memptr=cellptr,
        memval=cells[cellptr], memory=list(cells),
        next_input=input_iter.peek(null_value),
        output_buffer=list(output_buffer)))

  return EvalResult(
      output=output_buffer,
      success=success,
      failure_reason=reason,
      steps=steps,
      time=time.time() - start_time,
      memory=cells if output_memory else None,
      program_trace=program_trace)



#This file: utils_test.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Tests for common.utils.
"""

from collections import Counter
import random
import tempfile
import numpy as np
import tensorflow as tf

from common import utils  # brain coder


class UtilsTest(tf.test.TestCase):

  def testStackPad(self):
    # 1D.
    tensors = [[1, 2, 3], [4, 5, 6, 7, 8], [9]]
    result = utils.stack_pad(tensors, pad_axes=0, pad_to_lengths=6)
    self.assertTrue(np.array_equal(
        result,
        np.asarray([[1, 2, 3, 0, 0, 0],
                    [4, 5, 6, 7, 8, 0],
                    [9, 0, 0, 0, 0, 0]], dtype=np.float32)))

    # 3D.
    tensors = [[[[1, 2, 3], [4, 5, 6]]],
               [[[7, 8, 9], [0, 1, 2]], [[3, 4, 5], [6, 7, 8]]],
               [[[0, 1, 2]], [[3, 4, 5]]]]
    result = utils.stack_pad(tensors, pad_axes=[0, 1], pad_to_lengths=[2, 2])
    self.assertTrue(np.array_equal(
        result,
        np.asarray([[[[1, 2, 3], [4, 5, 6]],
                     [[0, 0, 0], [0, 0, 0]]],
                    [[[7, 8, 9], [0, 1, 2]],
                     [[3, 4, 5], [6, 7, 8]]],
                    [[[0, 1, 2], [0, 0, 0]],
                     [[3, 4, 5], [0, 0, 0]]]], dtype=np.float32)))

  def testStackPadNoAxes(self):
    # 2D.
    tensors = [[[1, 2, 3], [4, 5, 6]],
               [[7, 8, 9], [1, 2, 3]],
               [[4, 5, 6], [7, 8, 9]]]
    result = utils.stack_pad(tensors)
    self.assertTrue(np.array_equal(
        result,
        np.asarray(tensors)))

  def testStackPadNoneLength(self):
    # 1D.
    tensors = [[1, 2, 3], [4, 5, 6, 7, 8], [9]]
    result = utils.stack_pad(tensors, pad_axes=0, pad_to_lengths=None)
    self.assertTrue(np.array_equal(
        result,
        np.asarray([[1, 2, 3, 0, 0],
                    [4, 5, 6, 7, 8],
                    [9, 0, 0, 0, 0]], dtype=np.float32)))

    # 3D.
    tensors = [[[[1, 2, 3], [4, 5, 6]]],
               [[[7, 8, 9], [0, 1, 2]], [[3, 4, 5], [6, 7, 8]]],
               [[[0, 1, 2]], [[3, 4, 5]]]]
    result = utils.stack_pad(tensors, pad_axes=[0, 1], pad_to_lengths=None)
    self.assertTrue(np.array_equal(
        result,
        np.asarray([[[[1, 2, 3], [4, 5, 6]],
                     [[0, 0, 0], [0, 0, 0]]],
                    [[[7, 8, 9], [0, 1, 2]],
                     [[3, 4, 5], [6, 7, 8]]],
                    [[[0, 1, 2], [0, 0, 0]],
                     [[3, 4, 5], [0, 0, 0]]]], dtype=np.float32)))

    # 3D with partial pad_to_lengths.
    tensors = [[[[1, 2, 3], [4, 5, 6]]],
               [[[7, 8, 9], [0, 1, 2]], [[3, 4, 5], [6, 7, 8]]],
               [[[0, 1, 2]], [[3, 4, 5]]]]
    result = utils.stack_pad(tensors, pad_axes=[0, 1], pad_to_lengths=[None, 3])
    self.assertTrue(np.array_equal(
        result,
        np.asarray([[[[1, 2, 3], [4, 5, 6], [0, 0, 0]],
                     [[0, 0, 0], [0, 0, 0], [0, 0, 0]]],
                    [[[7, 8, 9], [0, 1, 2], [0, 0, 0]],
                     [[3, 4, 5], [6, 7, 8], [0, 0, 0]]],
                    [[[0, 1, 2], [0, 0, 0], [0, 0, 0]],
                     [[3, 4, 5], [0, 0, 0], [0, 0, 0]]]], dtype=np.float32)))

  def testStackPadValueError(self):
    # 3D.
    tensors = [[[[1, 2, 3], [4, 5, 6]]],
               [[[7, 8, 9], [0, 1, 2]], [[3, 4, 5], [6, 7, 8]]],
               [[[0, 1, 2]], [[3, 4, 5]]],
               [[[1, 2, 3, 4]]]]

    # Not all tensors have the same shape along axis 2.
    with self.assertRaises(ValueError):
      utils.stack_pad(tensors, pad_axes=[0, 1], pad_to_lengths=[2, 2])

  def testRecord(self):
    my_record = utils.make_record('my_record', ['a', 'b', 'c'], {'b': 55})
    inst = my_record(a=1, b=2, c=3)
    self.assertEqual(1, inst.a)
    self.assertEqual(2, inst.b)
    self.assertEqual(3, inst.c)
    self.assertEqual(1, inst[0])
    self.assertEqual(2, inst[1])
    self.assertEqual(3, inst[2])
    self.assertEqual([1, 2, 3], list(iter(inst)))
    self.assertEqual(3, len(inst))

    inst.b = 999
    self.assertEqual(999, inst.b)
    self.assertEqual(999, inst[1])

    inst2 = my_record(1, 999, 3)
    self.assertTrue(inst == inst2)
    inst2[1] = 3
    self.assertFalse(inst == inst2)

    inst3 = my_record(a=1, c=3)
    inst.b = 55
    self.assertEqual(inst, inst3)

  def testRecordUnique(self):
    record1 = utils.make_record('record1', ['a', 'b', 'c'])
    record2 = utils.make_record('record2', ['a', 'b', 'c'])
    self.assertNotEqual(record1(1, 2, 3), record2(1, 2, 3))
    self.assertEqual(record1(1, 2, 3), record1(1, 2, 3))

  def testTupleToRecord(self):
    my_record = utils.make_record('my_record', ['a', 'b', 'c'])
    inst = utils.tuple_to_record((5, 6, 7), my_record)
    self.assertEqual(my_record(5, 6, 7), inst)

  def testRecordErrors(self):
    my_record = utils.make_record('my_record', ['a', 'b', 'c'], {'b': 10})

    with self.assertRaises(ValueError):
      my_record(c=5)  # Did not provide required argument 'a'.
    with self.assertRaises(ValueError):
      my_record(1, 2, 3, 4)  # Too many arguments.

  def testRandomQueue(self):
    np.random.seed(567890)
    queue = utils.RandomQueue(5)
    queue.push(5)
    queue.push(6)
    queue.push(7)
    queue.push(8)
    queue.push(9)
    queue.push(10)
    self.assertTrue(5 not in queue)
    sample = queue.random_sample(1000)
    self.assertEqual(1000, len(sample))
    self.assertEqual([6, 7, 8, 9, 10], sorted(np.unique(sample).tolist()))

  def testMaxUniquePriorityQueue(self):
    queue = utils.MaxUniquePriorityQueue(5)
    queue.push(1.0, 'string 1')
    queue.push(-0.5, 'string 2')
    queue.push(0.5, 'string 3')
    self.assertEqual((-0.5, 'string 2', None), queue.pop())
    queue.push(0.1, 'string 4')
    queue.push(1.5, 'string 5')
    queue.push(0.0, 'string 6')
    queue.push(0.2, 'string 7')
    self.assertEqual((1.5, 'string 5', None), queue.get_max())
    self.assertEqual((0.1, 'string 4', None), queue.get_min())
    self.assertEqual(
        [('string 5', None), ('string 1', None), ('string 3', None),
         ('string 7', None), ('string 4', None)],
        list(queue.iter_in_order()))

  def testMaxUniquePriorityQueue_Duplicates(self):
    queue = utils.MaxUniquePriorityQueue(5)
    queue.push(0.0, 'string 1')
    queue.push(0.0, 'string 2')
    queue.push(0.0, 'string 3')
    self.assertEqual((0.0, 'string 1', None), queue.pop())
    self.assertEqual((0.0, 'string 2', None), queue.pop())
    self.assertEqual((0.0, 'string 3', None), queue.pop())
    self.assertEqual(0, len(queue))
    queue.push(0.1, 'string 4')
    queue.push(1.5, 'string 5')
    queue.push(0.3, 'string 6')
    queue.push(0.2, 'string 7')
    queue.push(0.0, 'string 8')
    queue.push(1.5, 'string 5')
    queue.push(1.5, 'string 5')
    self.assertEqual((1.5, 'string 5', None), queue.get_max())
    self.assertEqual((0.0, 'string 8', None), queue.get_min())
    self.assertEqual(
        [('string 5', None), ('string 6', None), ('string 7', None),
         ('string 4', None), ('string 8', None)],
        list(queue.iter_in_order()))

  def testMaxUniquePriorityQueue_ExtraData(self):
    queue = utils.MaxUniquePriorityQueue(5)
    queue.push(1.0, 'string 1', [1, 2, 3])
    queue.push(0.5, 'string 2', [4, 5, 6])
    queue.push(0.5, 'string 3', [7, 8, 9])
    queue.push(0.5, 'string 2', [10, 11, 12])
    self.assertEqual((0.5, 'string 2', [4, 5, 6]), queue.pop())
    self.assertEqual((0.5, 'string 3', [7, 8, 9]), queue.pop())
    self.assertEqual((1.0, 'string 1', [1, 2, 3]), queue.pop())
    self.assertEqual(0, len(queue))
    queue.push(0.5, 'string 2', [10, 11, 12])
    self.assertEqual((0.5, 'string 2', [10, 11, 12]), queue.pop())

  def testRouletteWheel(self):
    random.seed(12345678987654321)
    r = utils.RouletteWheel()
    self.assertTrue(r.is_empty())
    with self.assertRaises(RuntimeError):
      r.sample()  # Cannot sample when empty.
    self.assertEqual(0, r.total_weight)
    self.assertEqual(True, r.add('a', 0.1))
    self.assertFalse(r.is_empty())
    self.assertEqual(0.1, r.total_weight)
    self.assertEqual(True, r.add('b', 0.01))
    self.assertEqual(0.11, r.total_weight)
    self.assertEqual(True, r.add('c', 0.5))
    self.assertEqual(True, r.add('d', 0.1))
    self.assertEqual(True, r.add('e', 0.05))
    self.assertEqual(True, r.add('f', 0.03))
    self.assertEqual(True, r.add('g', 0.001))
    self.assertEqual(0.791, r.total_weight)
    self.assertFalse(r.is_empty())

    # Check that sampling is correct.
    obj, weight = r.sample()
    self.assertTrue(isinstance(weight, float), 'Type: %s' % type(weight))
    self.assertTrue((obj, weight) in r)
    for obj, weight in r.sample_many(100):
      self.assertTrue(isinstance(weight, float), 'Type: %s' % type(weight))
      self.assertTrue((obj, weight) in r)

    # Check that sampling distribution is correct.
    n = 1000000
    c = Counter(r.sample_many(n))
    for obj, w in r:
      estimated_w = c[(obj, w)] / float(n) * r.total_weight
      self.assertTrue(
          np.isclose(w, estimated_w, atol=1e-3),
          'Expected %s, got %s, for object %s' % (w, estimated_w, obj))

  def testRouletteWheel_AddMany(self):
    random.seed(12345678987654321)
    r = utils.RouletteWheel()
    self.assertTrue(r.is_empty())
    with self.assertRaises(RuntimeError):
      r.sample()  # Cannot sample when empty.
    self.assertEqual(0, r.total_weight)
    count = r.add_many(
        ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
        [0.1, 0.01, 0.5, 0.1, 0.05, 0.03, 0.001])
    self.assertEqual(7, count)
    self.assertFalse(r.is_empty())
    self.assertEqual(0.791, r.total_weight)

    # Adding no items is allowed.
    count = r.add_many([], [])
    self.assertEqual(0, count)
    self.assertFalse(r.is_empty())
    self.assertEqual(0.791, r.total_weight)

    # Check that sampling is correct.
    obj, weight = r.sample()
    self.assertTrue(isinstance(weight, float), 'Type: %s' % type(weight))
    self.assertTrue((obj, weight) in r)
    for obj, weight in r.sample_many(100):
      self.assertTrue(isinstance(weight, float), 'Type: %s' % type(weight))
      self.assertTrue((obj, weight) in r)

    # Check that sampling distribution is correct.
    n = 1000000
    c = Counter(r.sample_many(n))
    for obj, w in r:
      estimated_w = c[(obj, w)] / float(n) * r.total_weight
      self.assertTrue(
          np.isclose(w, estimated_w, atol=1e-3),
          'Expected %s, got %s, for object %s' % (w, estimated_w, obj))

  def testRouletteWheel_AddZeroWeights(self):
    r = utils.RouletteWheel()
    self.assertEqual(True, r.add('a', 0))
    self.assertFalse(r.is_empty())
    self.assertEqual(4, r.add_many(['b', 'c', 'd', 'e'], [0, 0.1, 0, 0]))
    self.assertEqual(
        [('a', 0.0), ('b', 0.0), ('c', 0.1), ('d', 0.0), ('e', 0.0)],
        list(r))

  def testRouletteWheel_UniqueMode(self):
    random.seed(12345678987654321)
    r = utils.RouletteWheel(unique_mode=True)
    self.assertEqual(True, r.add([1, 2, 3], 1, 'a'))
    self.assertEqual(True, r.add([4, 5], 0.5, 'b'))
    self.assertEqual(False, r.add([1, 2, 3], 1.5, 'a'))
    self.assertEqual(
        [([1, 2, 3], 1.0), ([4, 5], 0.5)],
        list(r))
    self.assertEqual(1.5, r.total_weight)
    self.assertEqual(
        2,
        r.add_many(
            [[5, 6, 2, 3], [1, 2, 3], [8], [1, 2, 3]],
            [0.1, 0.2, 0.1, 2.0],
            ['c', 'a', 'd', 'a']))
    self.assertEqual(
        [([1, 2, 3], 1.0), ([4, 5], 0.5), ([5, 6, 2, 3], 0.1), ([8], 0.1)],
        list(r))
    self.assertTrue(np.isclose(1.7, r.total_weight))
    self.assertEqual(0, r.add_many([], [], []))  # Adding no items is allowed.
    with self.assertRaises(ValueError):
      # Key not given.
      r.add([7, 8, 9], 2.0)
    with self.assertRaises(ValueError):
      # Keys not given.
      r.add_many([[7, 8, 9], [10]], [2.0, 2.0])
    self.assertEqual(True, r.has_key('a'))
    self.assertEqual(True, r.has_key('b'))
    self.assertEqual(False, r.has_key('z'))
    self.assertEqual(1.0, r.get_weight('a'))
    self.assertEqual(0.5, r.get_weight('b'))

    r = utils.RouletteWheel(unique_mode=False)
    self.assertEqual(True, r.add([1, 2, 3], 1))
    self.assertEqual(True, r.add([4, 5], 0.5))
    self.assertEqual(True, r.add([1, 2, 3], 1.5))
    self.assertEqual(
        [([1, 2, 3], 1.0), ([4, 5], 0.5), ([1, 2, 3], 1.5)],
        list(r))
    self.assertEqual(3, r.total_weight)
    self.assertEqual(
        4,
        r.add_many(
            [[5, 6, 2, 3], [1, 2, 3], [8], [1, 2, 3]],
            [0.1, 0.2, 0.1, 0.2]))
    self.assertEqual(
        [([1, 2, 3], 1.0), ([4, 5], 0.5), ([1, 2, 3], 1.5),
         ([5, 6, 2, 3], 0.1), ([1, 2, 3], 0.2), ([8], 0.1), ([1, 2, 3], 0.2)],
        list(r))
    self.assertTrue(np.isclose(3.6, r.total_weight))
    with self.assertRaises(ValueError):
      # Key is given.
      r.add([7, 8, 9], 2.0, 'a')
    with self.assertRaises(ValueError):
      # Keys are given.
      r.add_many([[7, 8, 9], [10]], [2.0, 2.0], ['a', 'b'])

  def testRouletteWheel_IncrementalSave(self):
    f = tempfile.NamedTemporaryFile()
    r = utils.RouletteWheel(unique_mode=True, save_file=f.name)
    entries = [
        ([1, 2, 3], 0.1, 'a'),
        ([4, 5], 0.2, 'b'),
        ([6], 0.3, 'c'),
        ([7, 8, 9, 10], 0.25, 'd'),
        ([-1, -2], 0.15, 'e'),
        ([-3, -4, -5], 0.5, 'f')]

    self.assertTrue(r.is_empty())
    for i in range(0, len(entries), 2):
      r.add(*entries[i])
      r.add(*entries[i + 1])
      r.incremental_save()

      r2 = utils.RouletteWheel(unique_mode=True, save_file=f.name)
      self.assertEqual(i + 2, len(r2))
      count = 0
      for j, (obj, weight) in enumerate(r2):
        self.assertEqual(entries[j][0], obj)
        self.assertEqual(entries[j][1], weight)
        self.assertEqual(weight, r2.get_weight(entries[j][2]))
        count += 1
      self.assertEqual(i + 2, count)

if __name__ == '__main__':
  tf.test.main()

#This file: config_lib.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Objects for storing configuration and passing config into binaries.

Config class stores settings and hyperparameters for models, data, and anything
else that may be specific to a particular run.
"""

import ast
import itertools
from six.moves import xrange


class Config(dict):
  """Stores model configuration, hyperparameters, or dataset parameters."""

  def __getattr__(self, attr):
    return self[attr]

  def __setattr__(self, attr, value):
    self[attr] = value

  def pretty_str(self, new_lines=True, indent=2, final_indent=0):
    prefix = (' ' * indent) if new_lines else ''
    final_prefix = (' ' * final_indent) if new_lines else ''
    kv = ['%s%s=%s' % (prefix, k,
                       (repr(v) if not isinstance(v, Config)
                        else v.pretty_str(new_lines=new_lines,
                                          indent=indent+2,
                                          final_indent=indent)))
          for k, v in self.items()]
    if new_lines:
      return 'Config(\n%s\n%s)' % (',\n'.join(kv), final_prefix)
    else:
      return 'Config(%s)' % ', '.join(kv)

  def _update_iterator(self, *args, **kwargs):
    """Convert mixed input into an iterator over (key, value) tuples.

    Follows the dict.update call signature.

    Args:
      *args: (Optional) Pass a dict or iterable of (key, value) 2-tuples as
          an unnamed argument. Only one unnamed argument allowed.
      **kwargs: (Optional) Pass (key, value) pairs as named arguments, where the
          argument name is the key and the argument value is the value.

    Returns:
      An iterator over (key, value) tuples given in the input.

    Raises:
      TypeError: If more than one unnamed argument is given.
    """
    if len(args) > 1:
      raise TypeError('Expected at most 1 unnamed arguments, got %d'
                      % len(args))
    obj = args[0] if args else dict()
    if isinstance(obj, dict):
      return itertools.chain(obj.items(), kwargs.items())
    # Assume obj is an iterable of 2-tuples.
    return itertools.chain(obj, kwargs.items())

  def make_default(self, keys=None):
    """Convert OneOf objects into their default configs.

    Recursively calls into Config objects.

    Args:
      keys: Iterable of key names to check. If None, all keys in self will be
          used.
    """
    if keys is None:
      keys = self.keys()
    for k in keys:
      # Replace OneOf with its default value.
      if isinstance(self[k], OneOf):
        self[k] = self[k].default()
      # Recursively call into all Config objects, even those that came from
      # OneOf objects in the previous code line (for nested OneOf objects).
      if isinstance(self[k], Config):
        self[k].make_default()

  def update(self, *args, **kwargs):
    """Same as dict.update except nested Config objects are updated.

    Args:
      *args: (Optional) Pass a dict or list of (key, value) 2-tuples as unnamed
          argument.
      **kwargs: (Optional) Pass (key, value) pairs as named arguments, where the
          argument name is the key and the argument value is the value.
    """
    key_set = set(self.keys())
    for k, v in self._update_iterator(*args, **kwargs):
      if k in key_set:
        key_set.remove(k)  # This key is updated so exclude from make_default.
      if k in self and isinstance(self[k], Config) and isinstance(v, dict):
        self[k].update(v)
      elif k in self and isinstance(self[k], OneOf) and isinstance(v, dict):
        # Replace OneOf with the chosen config.
        self[k] = self[k].update(v)
      else:
        self[k] = v
    self.make_default(key_set)

  def strict_update(self, *args, **kwargs):
    """Same as Config.update except keys and types are not allowed to change.

    If a given key is not already in this instance, an exception is raised. If a
    given value does not have the same type as the existing value for the same
    key, an exception is raised. Use this method to catch config mistakes.

    Args:
      *args: (Optional) Pass a dict or list of (key, value) 2-tuples as unnamed
          argument.
      **kwargs: (Optional) Pass (key, value) pairs as named arguments, where the
          argument name is the key and the argument value is the value.

    Raises:
      TypeError: If more than one unnamed argument is given.
      TypeError: If new value type does not match existing type.
      KeyError: If a given key is not already defined in this instance.
    """
    key_set = set(self.keys())
    for k, v in self._update_iterator(*args, **kwargs):
      if k in self:
        key_set.remove(k)  # This key is updated so exclude from make_default.
        if isinstance(self[k], Config):
          if not isinstance(v, dict):
            raise TypeError('dict required for Config value, got %s' % type(v))
          self[k].strict_update(v)
        elif isinstance(self[k], OneOf):
          if not isinstance(v, dict):
            raise TypeError('dict required for OneOf value, got %s' % type(v))
          # Replace OneOf with the chosen config.
          self[k] = self[k].strict_update(v)
        else:
          if not isinstance(v, type(self[k])):
            raise TypeError('Expecting type %s for key %s, got type %s'
                            % (type(self[k]), k, type(v)))
          self[k] = v
      else:
        raise KeyError(
            'Key %s does not exist. New key creation not allowed in '
            'strict_update.' % k)
    self.make_default(key_set)

  @staticmethod
  def from_str(config_str):
    """Inverse of Config.__str__."""
    parsed = ast.literal_eval(config_str)
    assert isinstance(parsed, dict)

    def _make_config(dictionary):
      for k, v in dictionary.items():
        if isinstance(v, dict):
          dictionary[k] = _make_config(v)
      return Config(**dictionary)
    return _make_config(parsed)

  @staticmethod
  def parse(key_val_string):
    """Parse hyperparameter string into Config object.

    Format is 'key=val,key=val,...'
    Values can be any python literal, or another Config object encoded as
    'c(key=val,key=val,...)'.
    c(...) expressions can be arbitrarily nested.

    Example:
    'a=1,b=3e-5,c=[1,2,3],d="hello world",e={"a":1,"b":2},f=c(x=1,y=[10,20])'

    Args:
      key_val_string: The hyperparameter string.

    Returns:
      Config object parsed from the input string.
    """
    if not key_val_string.strip():
      return Config()
    def _pair_to_kv(pair):
      split_index = pair.find('=')
      key, val = pair[:split_index].strip(), pair[split_index+1:].strip()
      if val.startswith('c(') and val.endswith(')'):
        val = Config.parse(val[2:-1])
      else:
        val = ast.literal_eval(val)
      return key, val
    return Config(**dict([_pair_to_kv(pair)
                          for pair in _comma_iterator(key_val_string)]))


class OneOf(object):
  """Stores branching config.

  In some cases there may be options which each have their own set of config
  params. For example, if specifying config for an environment, each environment
  can have custom config options. OneOf is a way to organize branching config.

  Usage example:
  one_of = OneOf(
      [Config(a=1, b=2),
       Config(a=2, c='hello'),
       Config(a=3, d=10, e=-10)],
      a=1)
  config = one_of.strict_update(Config(a=3, d=20))
  config == {'a': 3, 'd': 20, 'e': -10}
  """

  def __init__(self, choices, **kwargs):
    """Constructor.

    Usage: OneOf([Config(...), Config(...), ...], attribute=default_value)

    Args:
      choices: An iterable of Config objects. When update/strict_update is
          called on this OneOf, one of these Config will be selected.
      **kwargs: Give exactly one config attribute to branch on. The value of
          this attribute during update/strict_update will determine which
          Config is used.

    Raises:
      ValueError: If kwargs does not contain exactly one entry. Should give one
          named argument which is used as the attribute to condition on.
    """
    if len(kwargs) != 1:
      raise ValueError(
          'Incorrect usage. Must give exactly one named argument. The argument '
          'name is the config attribute to condition on, and the argument '
          'value is the default choice. Got %d named arguments.' % len(kwargs))
    key, default_value = kwargs.items()[0]
    self.key = key
    self.default_value = default_value

    # Make sure each choice is a Config object.
    for config in choices:
      if not isinstance(config, Config):
        raise TypeError('choices must be a list of Config objects. Got %s.'
                        % type(config))

    # Map value for key to the config with that value.
    self.value_map = {config[key]: config for config in choices}
    self.default_config = self.value_map[self.default_value]

    # Make sure there are no duplicate values.
    if len(self.value_map) != len(choices):
      raise ValueError('Multiple choices given for the same value of %s.' % key)

    # Check that the default value is valid.
    if self.default_value not in self.value_map:
      raise ValueError(
          'Default value is not an available choice. Got %s=%s. Choices are %s.'
          % (key, self.default_value, self.value_map.keys()))

  def default(self):
    return self.default_config

  def update(self, other):
    """Choose a config and update it.

    If `other` is a Config, one of the config choices is selected and updated.
    Otherwise `other` is returned.

    Args:
      other: Will update chosen config with this value by calling `update` on
          the config.

    Returns:
      The chosen config after updating it, or `other` if no config could be
      selected.
    """
    if not isinstance(other, Config):
      return other
    if self.key not in other or other[self.key] not in self.value_map:
      return other
    target = self.value_map[other[self.key]]
    target.update(other)
    return target

  def strict_update(self, config):
    """Choose a config and update it.

    `config` must be a Config object. `config` must have the key used to select
    among the config choices, and that key must have a value which one of the
    config choices has.

    Args:
      config: A Config object. the chosen config will be update by calling
           `strict_update`.

    Returns:
      The chosen config after updating it.

    Raises:
      TypeError: If `config` is not a Config instance.
      ValueError: If `config` does not have the branching key in its key set.
      ValueError: If the value of the config's branching key is not one of the
          valid choices.
    """
    if not isinstance(config, Config):
      raise TypeError('Expecting Config instance, got %s.' % type(config))
    if self.key not in config:
      raise ValueError(
          'Branching key %s required but not found in %s' % (self.key, config))
    if config[self.key] not in self.value_map:
      raise ValueError(
          'Value %s for key %s is not a possible choice. Choices are %s.'
          % (config[self.key], self.key, self.value_map.keys()))
    target = self.value_map[config[self.key]]
    target.strict_update(config)
    return target


def _next_comma(string, start_index):
  """Finds the position of the next comma not used in a literal collection."""
  paren_count = 0
  for i in xrange(start_index, len(string)):
    c = string[i]
    if c == '(' or c == '[' or c == '{':
      paren_count += 1
    elif c == ')' or c == ']' or c == '}':
      paren_count -= 1
    if paren_count == 0 and c == ',':
      return i
  return -1


def _comma_iterator(string):
  index = 0
  while 1:
    next_index = _next_comma(string, index)
    if next_index == -1:
      yield string[index:]
      return
    yield string[index:next_index]
    index = next_index + 1

#This file: reward_test.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Tests for common.reward."""

from math import log
import numpy as np
import tensorflow as tf

from common import reward  # brain coder


class RewardTest(tf.test.TestCase):

  def testAbsDiff(self):
    self.assertEqual(5, reward.abs_diff(15, 20))
    self.assertEqual(5, reward.abs_diff(20, 15))

  def testModAbsDiff(self):
    self.assertEqual(5, reward.mod_abs_diff(15, 20, 25))
    self.assertEqual(5, reward.mod_abs_diff(20, 15, 25))
    self.assertEqual(2, reward.mod_abs_diff(1, 24, 25))
    self.assertEqual(2, reward.mod_abs_diff(24, 1, 25))

    self.assertEqual(0, reward.mod_abs_diff(0, 0, 5))
    self.assertEqual(1, reward.mod_abs_diff(0, 1, 5))
    self.assertEqual(2, reward.mod_abs_diff(0, 2, 5))
    self.assertEqual(2, reward.mod_abs_diff(0, 3, 5))
    self.assertEqual(1, reward.mod_abs_diff(0, 4, 5))

    self.assertEqual(0, reward.mod_abs_diff(-1, 4, 5))
    self.assertEqual(1, reward.mod_abs_diff(-5, 4, 5))
    self.assertEqual(1, reward.mod_abs_diff(-7, 4, 5))
    self.assertEqual(1, reward.mod_abs_diff(13, 4, 5))
    self.assertEqual(1, reward.mod_abs_diff(15, 4, 5))

  def testAbsoluteDistance_AbsDiffMethod(self):
    self.assertEqual(
        4,
        reward.absolute_distance([0], [4], 5, scalar_diff_fn=reward.abs_diff))
    self.assertEqual(
        0,
        reward.absolute_distance([4], [4], 5, scalar_diff_fn=reward.abs_diff))
    self.assertEqual(
        0,
        reward.absolute_distance([], [], 5, scalar_diff_fn=reward.abs_diff))
    self.assertEqual(
        5,
        reward.absolute_distance([1], [], 5, scalar_diff_fn=reward.abs_diff))
    self.assertEqual(
        5,
        reward.absolute_distance([], [1], 5, scalar_diff_fn=reward.abs_diff))
    self.assertEqual(
        0,
        reward.absolute_distance([1, 2, 3], [1, 2, 3], 5,
                                 scalar_diff_fn=reward.abs_diff))
    self.assertEqual(
        1,
        reward.absolute_distance([1, 2, 4], [1, 2, 3], 5,
                                 scalar_diff_fn=reward.abs_diff))
    self.assertEqual(
        1,
        reward.absolute_distance([1, 2, 2], [1, 2, 3], 5,
                                 scalar_diff_fn=reward.abs_diff))
    self.assertEqual(
        5,
        reward.absolute_distance([1, 2], [1, 2, 3], 5,
                                 scalar_diff_fn=reward.abs_diff))
    self.assertEqual(
        5,
        reward.absolute_distance([1, 2, 3, 4], [1, 2, 3], 5,
                                 scalar_diff_fn=reward.abs_diff))
    self.assertEqual(
        6,
        reward.absolute_distance([4, 4, 4], [1, 2, 3], 5,
                                 scalar_diff_fn=reward.abs_diff))

  def testAbsoluteDistance_ModDiffMethod(self):
    self.assertEqual(
        1,
        reward.absolute_distance([0], [4], 5,
                                 scalar_diff_fn=reward.mod_abs_diff))
    self.assertEqual(
        0,
        reward.absolute_distance([4], [4], 5,
                                 scalar_diff_fn=reward.mod_abs_diff))
    self.assertEqual(
        0,
        reward.absolute_distance([], [], 5,
                                 scalar_diff_fn=reward.mod_abs_diff))
    self.assertEqual(
        5,
        reward.absolute_distance([1], [], 5,
                                 scalar_diff_fn=reward.mod_abs_diff))
    self.assertEqual(
        5,
        reward.absolute_distance([], [1], 5,
                                 scalar_diff_fn=reward.mod_abs_diff))
    self.assertEqual(
        0,
        reward.absolute_distance([1, 2, 3], [1, 2, 3], 5,
                                 scalar_diff_fn=reward.mod_abs_diff))
    self.assertEqual(
        1,
        reward.absolute_distance([1, 2, 4], [1, 2, 3], 5,
                                 scalar_diff_fn=reward.mod_abs_diff))
    self.assertEqual(
        1,
        reward.absolute_distance([1, 2, 2], [1, 2, 3], 5,
                                 scalar_diff_fn=reward.mod_abs_diff))
    self.assertEqual(
        5,
        reward.absolute_distance([1, 2], [1, 2, 3], 5,
                                 scalar_diff_fn=reward.mod_abs_diff))
    self.assertEqual(
        5,
        reward.absolute_distance([1, 2, 3, 4], [1, 2, 3], 5,
                                 scalar_diff_fn=reward.mod_abs_diff))
    self.assertEqual(
        5,
        reward.absolute_distance([4, 4, 4], [1, 2, 3], 5,
                                 scalar_diff_fn=reward.mod_abs_diff))

  def testLogAbsoluteDistance(self):
    def log_diff(diff, base):
      return log(diff + 1) / log(base // 2 + 2)

    self.assertEqual(
        log_diff(1, 5),
        reward.log_absolute_distance([0], [4], 5))
    self.assertEqual(
        log_diff(2, 5),
        reward.log_absolute_distance([1], [4], 5))
    self.assertEqual(
        log_diff(2, 5),
        reward.log_absolute_distance([2], [4], 5))
    self.assertEqual(
        log_diff(1, 5),
        reward.log_absolute_distance([3], [4], 5))
    self.assertEqual(
        log_diff(3, 5),  # max_dist = base // 2 + 1 = 3
        reward.log_absolute_distance([], [4], 5))
    self.assertEqual(
        0 + log_diff(3, 5),  # max_dist = base // 2 + 1 = 3
        reward.log_absolute_distance([4, 4], [4], 5))
    self.assertEqual(
        0,
        reward.log_absolute_distance([4], [4], 5))
    self.assertEqual(
        0,
        reward.log_absolute_distance([], [], 5))
    self.assertEqual(
        1,
        reward.log_absolute_distance([1], [], 5))
    self.assertEqual(
        1,
        reward.log_absolute_distance([], [1], 5))

    self.assertEqual(
        0,
        reward.log_absolute_distance([1, 2, 3], [1, 2, 3], 5))
    self.assertEqual(
        log_diff(1, 5) / 3,  # divided by target length.
        reward.log_absolute_distance([1, 2, 4], [1, 2, 3], 5))
    self.assertEqual(
        log_diff(1, 5) / 3,
        reward.log_absolute_distance([1, 2, 2], [1, 2, 3], 5))
    self.assertEqual(
        log_diff(3, 5) / 3,  # max_dist
        reward.log_absolute_distance([1, 2], [1, 2, 3], 5))
    self.assertEqual(
        log_diff(3, 5) / 3,  # max_dist
        reward.log_absolute_distance([1, 2, 3, 4], [1, 2, 3], 5))
    # Add log differences for each position.
    self.assertEqual(
        (log_diff(2, 5) + log_diff(2, 5) + log_diff(1, 5)) / 3,
        reward.log_absolute_distance([4, 4, 4], [1, 2, 3], 5))

  def testAbsoluteDistanceReward(self):
    self.assertEqual(
        1,
        reward.absolute_distance_reward([1, 2, 3], [1, 2, 3], 5))
    self.assertEqual(
        1 - 1 / (5 * 3.),  # 1 - distance / (base * target_len)
        reward.absolute_distance_reward([1, 2, 4], [1, 2, 3], 5))
    self.assertEqual(
        1 - 1 / (5 * 3.),
        reward.absolute_distance_reward([1, 2, 2], [1, 2, 3], 5))
    self.assertTrue(np.isclose(
        1 - 5 / (5 * 3.),
        reward.absolute_distance_reward([1, 2], [1, 2, 3], 5)))
    self.assertTrue(np.isclose(
        1 - 5 / (5 * 3.),
        reward.absolute_distance_reward([1, 2, 3, 4], [1, 2, 3], 5)))
    # Add log differences for each position.
    self.assertEqual(
        1 - (3 + 2 + 1) / (5 * 3.),
        reward.absolute_distance_reward([4, 4, 4], [1, 2, 3], 5))
    self.assertEqual(
        1,
        reward.absolute_distance_reward([], [], 5))

  def testAbsoluteModDistanceReward(self):
    self.assertEqual(
        1,
        reward.absolute_mod_distance_reward([1, 2, 3], [1, 2, 3], 5))
    self.assertEqual(
        1 - 1 / (5 * 3.),  # 1 - distance / (base * target_len)
        reward.absolute_mod_distance_reward([1, 2, 4], [1, 2, 3], 5))
    self.assertEqual(
        1 - 1 / (5 * 3.),
        reward.absolute_mod_distance_reward([1, 2, 2], [1, 2, 3], 5))
    self.assertTrue(np.isclose(
        1 - 5 / (5 * 3.),
        reward.absolute_mod_distance_reward([1, 2], [1, 2, 3], 5)))
    self.assertTrue(np.isclose(
        1 - 5 / (5 * 3.),
        reward.absolute_mod_distance_reward([1, 2, 3, 4], [1, 2, 3], 5)))
    # Add log differences for each position.
    self.assertTrue(np.isclose(
        1 - (2 + 2 + 1) / (5 * 3.),
        reward.absolute_mod_distance_reward([4, 4, 4], [1, 2, 3], 5)))
    self.assertTrue(np.isclose(
        1 - (1 + 2 + 2) / (5 * 3.),
        reward.absolute_mod_distance_reward([0, 1, 2], [4, 4, 4], 5)))
    self.assertEqual(
        1,
        reward.absolute_mod_distance_reward([], [], 5))

  def testAbsoluteLogDistanceReward(self):
    def log_diff(diff, base):
      return log(diff + 1) / log(base // 2 + 2)

    self.assertEqual(
        1,
        reward.absolute_log_distance_reward([1, 2, 3], [1, 2, 3], 5))
    self.assertEqual(
        1 - log_diff(1, 5) / 3,  # divided by target length.
        reward.absolute_log_distance_reward([1, 2, 4], [1, 2, 3], 5))
    self.assertEqual(
        1 - log_diff(1, 5) / 3,
        reward.absolute_log_distance_reward([1, 2, 2], [1, 2, 3], 5))
    self.assertEqual(
        1 - log_diff(3, 5) / 3,  # max_dist
        reward.absolute_log_distance_reward([1, 2], [1, 2, 3], 5))
    self.assertEqual(
        1 - log_diff(3, 5) / 3,  # max_dist
        reward.absolute_log_distance_reward([1, 2, 3, 4], [1, 2, 3], 5))
    # Add log differences for each position.
    self.assertEqual(
        1 - (log_diff(2, 5) + log_diff(2, 5) + log_diff(1, 5)) / 3,
        reward.absolute_log_distance_reward([4, 4, 4], [1, 2, 3], 5))
    self.assertEqual(
        1 - (log_diff(1, 5) + log_diff(2, 5) + log_diff(2, 5)) / 3,
        reward.absolute_log_distance_reward([0, 1, 2], [4, 4, 4], 5))
    self.assertEqual(
        1,
        reward.absolute_log_distance_reward([], [], 5))

  def testDeltaRewardManager(self):
    reward_manager = reward.DeltaRewardManager(
        [1, 2, 3, 4], base=5, distance_fn=reward.absolute_distance)
    self.assertEqual(-3, reward_manager([1]))
    self.assertEqual(0, reward_manager([1]))
    self.assertEqual(4 / 5., reward_manager([1, 3]))
    self.assertEqual(-4 / 5, reward_manager([1]))
    self.assertEqual(3, reward_manager([1, 2, 3, 4]))
    self.assertEqual(-1, reward_manager([1, 2, 3]))
    self.assertEqual(0, reward_manager([1, 2, 3, 4, 3]))
    self.assertEqual(-1, reward_manager([1, 2, 3, 4, 3, 2]))
    self.assertEqual(2, reward_manager([1, 2, 3, 4]))
    self.assertEqual(0, reward_manager([1, 2, 3, 4]))
    self.assertEqual(0, reward_manager([1, 2, 3, 4]))

  def testFloorRewardMananger(self):
    reward_manager = reward.FloorRewardManager(
        [1, 2, 3, 4], base=5, distance_fn=reward.absolute_distance)
    self.assertEqual(1, reward_manager([1]))
    self.assertEqual(0, reward_manager([1]))
    self.assertEqual(4 / 5., reward_manager([1, 3]))
    self.assertEqual(0, reward_manager([1]))
    self.assertEqual(1 / 5., reward_manager([1, 2]))
    self.assertEqual(0, reward_manager([0, 1]))
    self.assertEqual(0, reward_manager([]))
    self.assertEqual(0, reward_manager([1, 2]))
    self.assertEqual(2, reward_manager([1, 2, 3, 4]))
    self.assertEqual(0, reward_manager([1, 2, 3]))
    self.assertEqual(-1, reward_manager([1, 2, 3, 4, 3]))
    self.assertEqual(0, reward_manager([1, 2, 3, 4, 3, 2]))
    self.assertEqual(1, reward_manager([1, 2, 3, 4]))
    self.assertEqual(0, reward_manager([1, 2, 3, 4]))
    self.assertEqual(0, reward_manager([1, 2, 3, 4]))

    reward_manager = reward.FloorRewardManager(
        [1, 2, 3, 4], base=5, distance_fn=reward.absolute_distance)
    self.assertEqual(1, reward_manager([1]))
    self.assertEqual(-1, reward_manager([1, 0, 0, 0, 0, 0]))
    self.assertEqual(0, reward_manager([1, 2, 3, 4, 0, 0]))
    self.assertEqual(0, reward_manager([1, 2, 3, 4, 0]))
    self.assertEqual(1, reward_manager([]))
    self.assertEqual(0, reward_manager([]))
    self.assertEqual(0, reward_manager([1]))
    self.assertEqual(1, reward_manager([1, 2]))
    self.assertEqual(-1, reward_manager([1, 2, 3, 4, 0, 0]))
    self.assertEqual(0, reward_manager([1, 1, 1, 1, 1]))
    self.assertEqual(1 + 2, reward_manager([1, 2, 3, 4]))


if __name__ == '__main__':
  tf.test.main()

#This file: utils.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Configuration class."""

import bisect
from collections import deque
import cPickle
import heapq
import random

from absl import logging
import numpy as np
import six
from six.moves import xrange
import tensorflow as tf


def tuple_to_record(tuple_, record_type):
  return record_type(**dict(zip(record_type.__slots__, tuple_)))


def make_record(type_name, attributes, defaults=None):
  """Factory for mutable record classes.

  A record acts just like a collections.namedtuple except slots are writable.
  One exception is that record classes are not equivalent to tuples or other
  record classes of the same length.

  Note, each call to `make_record` produces a unique type. Two calls will make
  different types even if `type_name` is the same each time.

  Args:
    type_name: Name of the record type to create.
    attributes: List of names of each record attribute. The order of the list
        is preserved.
    defaults: (optional) default values for attributes. A dict mapping attribute
        names to values.

  Returns:
    A new record type.

  Raises:
    ValueError: If,
        `defaults` is not a dict,
        `attributes` contains duplicate names,
        `defaults` keys are not contained in `attributes`.
  """
  if defaults is None:
    defaults = {}
  if not isinstance(defaults, dict):
    raise ValueError('defaults must be a dict.')
  attr_set = set(attributes)
  if len(attr_set) < len(attributes):
    raise ValueError('No duplicate attributes allowed.')
  if not set(defaults.keys()).issubset(attr_set):
    raise ValueError('Default attributes must be given in the attributes list.')

  class RecordClass(object):
    """A record type.

    Acts like mutable tuple with named slots.
    """
    __slots__ = list(attributes)
    _defaults = dict(defaults)

    def __init__(self, *args, **kwargs):
      if len(args) > len(self.__slots__):
        raise ValueError('Too many arguments. %s has length %d.'
                         % (type(self).__name__, len(self.__slots__)))
      for attr, val in self._defaults.items():
        setattr(self, attr, val)
      for i, arg in enumerate(args):
        setattr(self, self.__slots__[i], arg)
      for attr, val in kwargs.items():
        setattr(self, attr, val)
      for attr in self.__slots__:
        if not hasattr(self, attr):
          raise ValueError('Required attr "%s" is not set.' % attr)

    def __len__(self):
      return len(self.__slots__)

    def __iter__(self):
      for attr in self.__slots__:
        yield getattr(self, attr)

    def __getitem__(self, index):
      return getattr(self, self.__slots__[index])

    def __setitem__(self, index, value):
      return setattr(self, self.__slots__[index], value)

    def __eq__(self, other):
      # Types must be equal as well as values.
      return (isinstance(other, type(self))
              and all(a == b for a, b in zip(self, other)))

    def __str__(self):
      return '%s(%s)' % (
          type(self).__name__,
          ', '.join(attr + '=' + str(getattr(self, attr))
                    for attr in self.__slots__))

    def __repr__(self):
      return str(self)

  RecordClass.__name__ = type_name
  return RecordClass


# Making minibatches.
def stack_pad(tensors, pad_axes=None, pad_to_lengths=None, dtype=np.float32,
              pad_value=0):
  """Stack tensors along 0-th dim and pad them to be the same shape.

  Args:
    tensors: Any list of iterables (python list, numpy array, etc). Can be 1D
        or multi-D iterables.
    pad_axes: An int or list of ints. Axes to pad along.
    pad_to_lengths: Length in each dimension. If pad_axes was an int, this is an
        int or None. If pad_axes was a list of ints, this is a list of mixed int
        and None types with the same length, or None. A None length means the
        maximum length among the given tensors is used.
    dtype: Type of output numpy array. Defaults to np.float32.
    pad_value: Value to use for padding. Defaults to 0.

  Returns:
    Numpy array containing the tensors stacked along the 0-th dimension and
        padded along the specified dimensions.

  Raises:
    ValueError: If the tensors do not have equal shapes along non-padded
        dimensions.
  """
  tensors = [np.asarray(t) for t in tensors]
  max_lengths = [max(l) for l in zip(*[t.shape for t in tensors])]
  same_axes = dict(enumerate(max_lengths))
  if pad_axes is None:
    pad_axes = []
  if isinstance(pad_axes, six.integer_types):
    if pad_to_lengths is not None:
      max_lengths[pad_axes] = pad_to_lengths
    del same_axes[pad_axes]
  else:
    if pad_to_lengths is None:
      pad_to_lengths = [None] * len(pad_axes)
    for i, l in zip(pad_axes, pad_to_lengths):
      if l is not None:
        max_lengths[i] = l
      del same_axes[i]
  same_axes_items = same_axes.items()
  dest = np.full([len(tensors)] + max_lengths, pad_value, dtype=dtype)
  for i, t in enumerate(tensors):
    for j, l in same_axes_items:
      if t.shape[j] != l:
        raise ValueError(
            'Tensor at index %d does not have size %d along axis %d'
            % (i, l, j))
    dest[[i] + [slice(0, d) for d in t.shape]] = t
  return dest


class RandomQueue(deque):

  def __init__(self, capacity):
    super(RandomQueue, self).__init__([], capacity)
    self.capacity = capacity

  def random_sample(self, sample_size):
    idx = np.random.choice(len(self), sample_size)
    return [self[i] for i in idx]

  def push(self, item):
    # Append to right. Oldest element will be popped from left.
    self.append(item)


class MPQItemContainer(object):
  """Class for holding an item with its score.

  Defines a comparison function for use in the heap-queue.
  """

  def __init__(self, score, item, extra_data):
    self.item = item
    self.score = score
    self.extra_data = extra_data

  def __cmp__(self, other):
    assert isinstance(other, type(self))
    return cmp(self.score, other.score)

  def __iter__(self):
    """Allows unpacking like a tuple."""
    yield self.score
    yield self.item
    yield self.extra_data

  def __repr__(self):
    """String representation of this item.

    `extra_data` is not included in the representation. We are assuming that
    `extra_data` is not easily interpreted by a human (if it was, it should be
    hashable, like a string or tuple).

    Returns:
      String representation of `self`.
    """
    return str((self.score, self.item))

  def __str__(self):
    return repr(self)


class MaxUniquePriorityQueue(object):
  """A maximum priority queue where duplicates are not added.

  The top items by score remain in the queue. When the capacity is reached,
  the lowest scored item in the queue will be dropped.

  This implementation differs from a typical priority queue, in that the minimum
  score is popped, instead of the maximum. Largest scores remain stuck in the
  queue. This is useful for accumulating the best known items from a population.

  The items used to determine uniqueness must be hashable, but additional
  non-hashable data may be stored with each item.
  """

  def __init__(self, capacity):
    self.capacity = capacity
    self.heap = []
    self.unique_items = set()

  def push(self, score, item, extra_data=None):
    """Push an item onto the queue.

    If the queue is at capacity, the item with the smallest score will be
    dropped. Note that it is assumed each item has exactly one score. The same
    item with a different score will still be dropped.

    Args:
      score: Number used to prioritize items in the queue. Largest scores are
          kept in the queue.
      item: A hashable item to be stored. Duplicates of this item will not be
          added to the queue.
      extra_data: An extra (possible not hashable) data to store with the item.
    """
    if item in self.unique_items:
      return
    if len(self.heap) >= self.capacity:
      _, popped_item, _ = heapq.heappushpop(
          self.heap, MPQItemContainer(score, item, extra_data))
      self.unique_items.add(item)
      self.unique_items.remove(popped_item)
    else:
      heapq.heappush(self.heap, MPQItemContainer(score, item, extra_data))
      self.unique_items.add(item)

  def pop(self):
    """Pop the item with the lowest score.

    Returns:
      score: Item's score.
      item: The item that was popped.
      extra_data: Any extra data stored with the item.
    """
    if not self.heap:
      return ()
    score, item, extra_data = heapq.heappop(self.heap)
    self.unique_items.remove(item)
    return score, item, extra_data

  def get_max(self):
    """Peek at the item with the highest score.

    Returns:
      Same as `pop`.
    """
    if not self.heap:
      return ()
    score, item, extra_data = heapq.nlargest(1, self.heap)[0]
    return score, item, extra_data

  def get_min(self):
    """Peek at the item with the lowest score.

    Returns:
      Same as `pop`.
    """
    if not self.heap:
      return ()
    score, item, extra_data = heapq.nsmallest(1, self.heap)[0]
    return score, item, extra_data

  def random_sample(self, sample_size):
    """Randomly select items from the queue.

    This does not modify the queue.

    Items are drawn from a uniform distribution, and not weighted by score.

    Args:
      sample_size: Number of random samples to draw. The same item can be
          sampled multiple times.

    Returns:
      List of sampled items (of length `sample_size`). Each element in the list
      is a tuple: (item, extra_data).
    """
    idx = np.random.choice(len(self.heap), sample_size)
    return [(self.heap[i].item, self.heap[i].extra_data) for i in idx]

  def iter_in_order(self):
    """Iterate over items in the queue from largest score to smallest.

    Yields:
      item: Hashable item.
      extra_data: Extra data stored with the item.
    """
    for _, item, extra_data in heapq.nlargest(len(self.heap), self.heap):
      yield item, extra_data

  def __len__(self):
    return len(self.heap)

  def __iter__(self):
    for _, item, _ in self.heap:
      yield item

  def __repr__(self):
    return '[' + ', '.join(repr(c) for c in self.heap) + ']'

  def __str__(self):
    return repr(self)


class RouletteWheel(object):
  """Randomly samples stored objects proportionally to their given weights.

  Stores objects and weights. Acts like a roulette wheel where each object is
  given a slice of the roulette disk proportional to its weight.

  This can be used as a replay buffer where past experiences are sampled
  proportionally to their weights. A good choice of "weight" for reinforcement
  learning is exp(reward / temperature) where temperature -> inf makes the
  distribution more uniform and temperature -> 0 makes the distribution more
  peaky.

  To prevent experiences from being overweighted by appearing in the replay
  buffer multiple times, a "unique mode" is supported where duplicate
  experiences are ignored. In unique mode, weights can be quickly retrieved from
  keys.
  """

  def __init__(self, unique_mode=False, save_file=None):
    """Construct empty RouletteWheel.

    If `save_file` is not None, and the file already exists on disk, whatever
    is in the file will be loaded into this instance. This allows jobs using
    RouletteWheel to resume after preemption.

    Args:
      unique_mode: If True, puts this RouletteWheel into unique mode, where
          objects are added with hashable keys, so that duplicates are ignored.
      save_file: Optional file path to save to. Must be a string containing
          an absolute path to a file, or None. File will be Python pickle
          format.
    """
    self.unique_mode = unique_mode
    self.objects = []
    self.weights = []
    self.partial_sums = []
    if self.unique_mode:
      self.keys_to_weights = {}
    self.save_file = save_file
    self.save_to_disk_buffer = []

    if save_file is not None and tf.gfile.Exists(save_file):
      # Load from disk.
      with tf.gfile.OpenFast(save_file, 'r') as f:
        count = 0
        while 1:
          try:
            obj, weight, key = cPickle.load(f)
          except EOFError:
            break
          else:
            self.add(obj, weight, key)
            count += 1
      logging.info('Loaded %d samples from disk.', count)
      # Clear buffer since these items are already on disk.
      self.save_to_disk_buffer = []

  def __iter__(self):
    return iter(zip(self.objects, self.weights))

  def __len__(self):
    return len(self.objects)

  def is_empty(self):
    """Returns whether there is anything in the roulette wheel."""
    return not self.partial_sums

  @property
  def total_weight(self):
    """Total cumulative weight across all objects."""
    if self.partial_sums:
      return self.partial_sums[-1]
    return 0.0

  def has_key(self, key):
    if self.unique_mode:
      RuntimeError('has_key method can only be called in unique mode.')
    return key in self.keys_to_weights

  def get_weight(self, key):
    if self.unique_mode:
      RuntimeError('get_weight method can only be called in unique mode.')
    return self.keys_to_weights[key]

  def add(self, obj, weight, key=None):
    """Add one object and its weight to the roulette wheel.

    Args:
      obj: Any object to be stored.
      weight: A non-negative float. The given object will be drawn with
          probability proportional to this weight when sampling.
      key: This argument is only used when in unique mode. To allow `obj` to
          be an unhashable type, like list, a separate hashable key is given.
          Each `key` should be unique to each `obj`. `key` is used to check if
          `obj` has been added to the roulette wheel before.

    Returns:
      True if the object was added, False if it was not added due to it being
      a duplicate (this only happens in unique mode).

    Raises:
      ValueError: If `weight` is negative.
      ValueError: If `key` is not given when in unique mode, or if `key` is
          given when not in unique mode.
    """
    if weight < 0:
      raise ValueError('Weight must be non-negative')
    if self.unique_mode:
      if key is None:
        raise ValueError(
            'Hashable key required for objects when unique mode is enabled.')
      if key in self.keys_to_weights:
        # Weight updates are not allowed. Ignore the given value of `weight`.
        return False
      self.keys_to_weights[key] = weight
    elif key is not None:
      raise ValueError(
          'key argument should not be used when unique mode is disabled.')
    self.objects.append(obj)
    self.weights.append(weight)
    self.partial_sums.append(self.total_weight + weight)
    if self.save_file is not None:
      # Record new item in buffer.
      self.save_to_disk_buffer.append((obj, weight, key))
    return True

  def add_many(self, objs, weights, keys=None):
    """Add many object and their weights to the roulette wheel.

    Arguments are the same as the `add` method, except each is a list. Lists
    must all be the same length.

    Args:
      objs: List of objects to be stored.
      weights: List of non-negative floats. See `add` method.
      keys: List of hashable keys. This argument is only used when in unique
          mode. See `add` method.

    Returns:
      Number of objects added. This number will be less than the number of
      objects provided if we are in unique mode and some keys are already
      in the roulette wheel.

    Raises:
      ValueError: If `keys` argument is provided when unique_mode == False, or
          is not provided when unique_mode == True.
      ValueError: If any of the lists are not the same length.
      ValueError: If any of the weights are negative.
    """
    if keys is not None and not self.unique_mode:
      raise ValueError('Not in unique mode. Do not provide keys.')
    elif keys is None and self.unique_mode:
      raise ValueError('In unique mode. You must provide hashable keys.')
    if keys and len(objs) != len(keys):
      raise ValueError('Number of objects does not equal number of keys.')
    if len(objs) != len(weights):
      raise ValueError('Number of objects does not equal number of weights.')
    return sum([self.add(obj, weights[i], key=keys[i] if keys else None)
                for i, obj in enumerate(objs)])

  def sample(self):
    """Spin the roulette wheel.

    Randomly select an object with probability proportional to its weight.

    Returns:
      object: The selected object.
      weight: The weight of the selected object.

    Raises:
      RuntimeError: If the roulette wheel is empty.
    """
    if self.is_empty():
      raise RuntimeError('Trying to sample from empty roulette wheel.')
    spin = random.random() * self.total_weight

    # Binary search.
    i = bisect.bisect_right(self.partial_sums, spin)
    if i == len(self.partial_sums):
      # This should not happen since random.random() will always be strictly
      # less than 1.0, and the last partial sum equals self.total_weight().
      # However it may happen due to rounding error. In that case it is easy to
      # handle this, just select the last object.
      i -= 1

    return self.objects[i], self.weights[i]

  def sample_many(self, count):
    """Spin the roulette wheel `count` times and return the results."""
    if self.is_empty():
      raise RuntimeError('Trying to sample from empty roulette wheel.')
    return [self.sample() for _ in xrange(count)]

  def incremental_save(self, log_info=False):
    """Write new entries to disk.

    This performs an append operation on the `save_file` given in the
    constructor. Any entries added since the last call to `incremental_save`
    will be appended to the file.

    If a new RouletteWheel is constructed with the same `save_file`, all the
    entries written there will be automatically loaded into the instance.
    This is useful when a job resumes after preemption.

    Args:
      log_info: If True, info about this operation will be logged.

    Raises:
      RuntimeError: If `save_file` given in the constructor is None.
    """
    if self.save_file is None:
      raise RuntimeError('Cannot call incremental_save. `save_file` is None.')
    if log_info:
      logging.info('Saving %d new samples to disk.',
                   len(self.save_to_disk_buffer))
    with tf.gfile.OpenFast(self.save_file, 'a') as f:
      for entry in self.save_to_disk_buffer:
        cPickle.dump(entry, f)
    # Clear the buffer.
    self.save_to_disk_buffer = []

#This file: rollout.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Utilities related to computing training batches from episode rollouts.

Implementations here are based on code from Open AI:
https://github.com/openai/universe-starter-agent/blob/master/a3c.py.
"""

from collections import namedtuple
import numpy as np
import scipy.signal

from common import utils  # brain coder


class Rollout(object):
  """Holds a rollout for an episode.

  A rollout is a record of the states observed in some environment and actions
  taken by the agent to arrive at those states. Other information includes
  rewards received after each action, values estimated for each state, whether
  the rollout concluded the episide, and total reward received. Everything
  should be given in time order.

  At each time t, the agent sees state s_t, takes action a_t, and then receives
  reward r_t. The agent may optionally estimate a state value V(s_t) for each
  state.

  For an episode of length T:
  states = [s_0, ..., s_(T-1)]
  actions = [a_0, ..., a_(T-1)]
  rewards = [r_0, ..., r_(T-1)]
  values = [V(s_0), ..., V(s_(T-1))]

  Note that there is an extra state s_T observed after taking action a_(T-1),
  but this is not included in the rollout.

  Rollouts have an `terminated` attribute which is True when the rollout is
  "finalized", i.e. it holds a full episode. terminated will be False when
  time steps are still being added to it.
  """

  def __init__(self):
    self.states = []
    self.actions = []
    self.rewards = []
    self.values = []
    self.total_reward = 0.0
    self.terminated = False

  def add(self, state, action, reward, value=0.0, terminated=False):
    """Add the next timestep to this rollout.

    Args:
      state: The state observed at the start of this timestep.
      action: The action taken after observing the given state.
      reward: The reward received for taking the given action.
      value: The value estimated for the given state.
      terminated: Whether this timestep ends the episode.

    Raises:
      ValueError: If this.terminated is already True, meaning that the episode
          has already ended.
    """
    if self.terminated:
      raise ValueError(
          'Trying to add timestep to an already terminal rollout.')
    self.states += [state]
    self.actions += [action]
    self.rewards += [reward]
    self.values += [value]
    self.terminated = terminated
    self.total_reward += reward

  def add_many(self, states, actions, rewards, values=None, terminated=False):
    """Add many timesteps to this rollout.

    Arguments are the same as `add`, but are lists of equal size.

    Args:
      states: The states observed.
      actions: The actions taken.
      rewards: The rewards received.
      values: The values estimated for the given states.
      terminated: Whether this sequence ends the episode.

    Raises:
      ValueError: If the lengths of all the input lists are not equal.
      ValueError: If this.terminated is already True, meaning that the episode
          has already ended.
    """
    if len(states) != len(actions):
      raise ValueError(
          'Number of states and actions must be the same. Got %d states and '
          '%d actions' % (len(states), len(actions)))
    if len(states) != len(rewards):
      raise ValueError(
          'Number of states and rewards must be the same. Got %d states and '
          '%d rewards' % (len(states), len(rewards)))
    if values is not None and len(states) != len(values):
      raise ValueError(
          'Number of states and values must be the same. Got %d states and '
          '%d values' % (len(states), len(values)))
    if self.terminated:
      raise ValueError(
          'Trying to add timesteps to an already terminal rollout.')
    self.states += states
    self.actions += actions
    self.rewards += rewards
    self.values += values if values is not None else [0.0] * len(states)
    self.terminated = terminated
    self.total_reward += sum(rewards)

  def extend(self, other):
    """Append another rollout to this rollout."""
    assert not self.terminated
    self.states.extend(other.states)
    self.actions.extend(other.actions)
    self.rewards.extend(other.rewards)
    self.values.extend(other.values)
    self.terminated = other.terminated
    self.total_reward += other.total_reward


def discount(x, gamma):
  """Returns discounted sums for each value in x, with discount factor gamma.

  This can be used to compute the return (discounted sum of rewards) at each
  timestep given a sequence of rewards. See the definitions for return and
  REINFORCE in section 3 of https://arxiv.org/pdf/1602.01783.pdf.

  Let g^k mean gamma ** k.
  For list [x_0, ..., x_N], the following list of discounted sums is computed:
  [x_0 + g^1 * x_1 + g^2 * x_2 + ... g^N * x_N,
   x_1 + g^1 * x_2 + g^2 * x_3 + ... g^(N-1) * x_N,
   x_2 + g^1 * x_3 + g^2 * x_4 + ... g^(N-2) * x_N,
   ...,
   x_(N-1) + g^1 * x_N,
   x_N]

  Args:
    x: List of numbers [x_0, ..., x_N].
    gamma: Float between 0 and 1 (inclusive). This is the discount factor.

  Returns:
    List of discounted sums.
  """
  return scipy.signal.lfilter([1], [1, -gamma], x[::-1], axis=0)[::-1]


def discounted_advantage_and_rewards(rewards, values, gamma, lambda_=1.0):
  """Compute advantages and returns (discounted sum of rewards).

  For an episode of length T, rewards = [r_0, ..., r_(T-1)].
  Each reward r_t is observed after taking action a_t at state s_t. A final
  state s_T is observed but no reward is given at this state since no action
  a_T is taken (otherwise there would be a new state s_(T+1)).

  `rewards` and `values` are for a single episode. Return R_t is the discounted
  sum of future rewards starting at time t, where `gamma` is the discount
  factor.
  R_t = r_t + gamma * r_(t+1) + gamma**2 * r_(t+2) + ...
        + gamma**(T-1-t) * r_(T-1)

  Advantage A(a_t, s_t) is approximated by computing A(a_t, s_t) = R_t - V(s_t)
  where V(s_t) is an approximation of the value at that state, given in the
  `values` list. Returns R_t are needed for all REINFORCE algorithms. Advantage
  is used for the advantage actor critic variant of REINFORCE.
  See algorithm S3 in https://arxiv.org/pdf/1602.01783.pdf.

  Additionally another parameter `lambda_` controls the bias-variance tradeoff.
  See "Generalized Advantage Estimation": https://arxiv.org/abs/1506.02438.
  lambda_ = 1 reduces to regular advantage.
  0 <= lambda_ < 1 trades off variance for bias, with lambda_ = 0 being the
  most biased.

  Bootstrapping is also supported. If an episode does not end in a terminal
  state (either because the episode was ended early, or the environment does not
  have end states), the true return cannot be computed from the rewards alone.
  However, it can be estimated by computing the value (an approximation of
  return) of the last state s_T. Thus the `values` list will have an extra item:
  values = [V(s_0), ..., V(s_(T-1)), V(s_T)].

  Args:
    rewards: List of observed rewards [r_0, ..., r_(T-1)].
    values: List of estimated values [V(s_0), ..., V(s_(T-1))] with an optional
        extra V(s_T) item.
    gamma: Discount factor. Number between 0 and 1. 1 means no discount.
        If not 1, gamma is typically near 1, like 0.99.
    lambda_: Bias-variance tradeoff factor. Between 0 and 1.

  Returns:
    empirical_values: Returns at each timestep.
    generalized_advantage: Avantages at each timestep.

  Raises:
    ValueError: If shapes of `rewards` and `values` are not rank 1.
    ValueError: If len(values) not in (len(rewards), len(rewards) + 1).
  """
  rewards = np.asarray(rewards, dtype=np.float32)
  values = np.asarray(values, dtype=np.float32)
  if rewards.ndim != 1:
    raise ValueError('Single episode only. rewards must be rank 1.')
  if values.ndim != 1:
    raise ValueError('Single episode only. values must be rank 1.')
  if len(values) == len(rewards):
    # No bootstrapping.
    values = np.append(values, 0)
    empirical_values = discount(rewards, gamma)
  elif len(values) == len(rewards) + 1:
    # With bootstrapping.
    # Last value is for the terminal state (final state after last action was
    # taken).
    empirical_values = discount(np.append(rewards, values[-1]), gamma)[:-1]
  else:
    raise ValueError('values should contain the same number of items or one '
                     'more item than rewards')
  delta = rewards + gamma * values[1:] - values[:-1]
  generalized_advantage = discount(delta, gamma * lambda_)

  # empirical_values is the discounted sum of rewards into the future.
  # generalized_advantage is the target for each policy update.
  return empirical_values, generalized_advantage


"""Batch holds a minibatch of episodes.

Let bi = batch_index, i.e. the index of each episode in the minibatch.
Let t = time.

Attributes:
  states: States for each timestep in each episode. Indexed by states[bi, t].
  actions: Actions for each timestep in each episode. Indexed by actions[bi, t].
  discounted_adv: Advantages (computed by discounted_advantage_and_rewards)
      for each timestep in each episode. Indexed by discounted_adv[bi, t].
  discounted_r: Returns (discounted sum of rewards computed by
      discounted_advantage_and_rewards) for each timestep in each episode.
      Indexed by discounted_r[bi, t].
  total_rewards: Total reward for each episode, i.e. sum of rewards across all
      timesteps (not discounted). Indexed by total_rewards[bi].
  episode_lengths: Number of timesteps in each episode. If an episode has
      N actions, N rewards, and N states, then its length is N. Indexed by
      episode_lengths[bi].
  batch_size: Number of episodes in this minibatch. An integer.
  max_time: Maximum episode length in the batch. An integer.
"""  # pylint: disable=pointless-string-statement
Batch = namedtuple(
    'Batch',
    ['states', 'actions', 'discounted_adv', 'discounted_r', 'total_rewards',
     'episode_lengths', 'batch_size', 'max_time'])


def process_rollouts(rollouts, gamma, lambda_=1.0):
  """Convert a batch of rollouts into tensors ready to be fed into a model.

  Lists from each episode are stacked into 2D tensors and padded with 0s up to
  the maximum timestep in the batch.

  Args:
    rollouts: A list of Rollout instances.
    gamma: The discount factor. A number between 0 and 1 (inclusive). See gamma
        argument in discounted_advantage_and_rewards.
    lambda_: See lambda_ argument in discounted_advantage_and_rewards.

  Returns:
    Batch instance. states, actions, discounted_adv, and discounted_r are
    numpy arrays with shape (batch_size, max_episode_length). episode_lengths
    is a list of ints. total_rewards is a list of floats (total reward in each
    episode). batch_size and max_time are ints.

  Raises:
    ValueError: If any of the rollouts are not terminal.
  """
  for ro in rollouts:
    if not ro.terminated:
      raise ValueError('Can only process terminal rollouts.')

  episode_lengths = [len(ro.states) for ro in rollouts]
  batch_size = len(rollouts)
  max_time = max(episode_lengths)

  states = utils.stack_pad([ro.states for ro in rollouts], 0, max_time)
  actions = utils.stack_pad([ro.actions for ro in rollouts], 0, max_time)

  discounted_rewards = [None] * batch_size
  discounted_adv = [None] * batch_size
  for i, ro in enumerate(rollouts):
    disc_r, disc_adv = discounted_advantage_and_rewards(
        ro.rewards, ro.values, gamma, lambda_)
    discounted_rewards[i] = disc_r
    discounted_adv[i] = disc_adv
  discounted_rewards = utils.stack_pad(discounted_rewards, 0, max_time)
  discounted_adv = utils.stack_pad(discounted_adv, 0, max_time)

  total_rewards = [sum(ro.rewards) for ro in rollouts]

  return Batch(states=states,
               actions=actions,
               discounted_adv=discounted_adv,
               discounted_r=discounted_rewards,
               total_rewards=total_rewards,
               episode_lengths=episode_lengths,
               batch_size=batch_size,
               max_time=max_time)

#This file: rollout_test.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Tests for common.rollout."""

import numpy as np
import tensorflow as tf

from common import rollout as rollout_lib  # brain coder


class RolloutTest(tf.test.TestCase):

  def MakeRollout(self, states, actions, rewards, values=None, terminated=True):
    rollout = rollout_lib.Rollout()
    rollout.add_many(
        states=states, actions=actions, rewards=rewards, values=values,
        terminated=terminated)
    return rollout

  def testDiscount(self):
    discounted = np.array([1.0 / 2 ** n for n in range(4, -1, -1)])
    discounted[:2] += [1.0 / 2 ** n for n in range(1, -1, -1)]

    self.assertTrue(np.array_equal(
        rollout_lib.discount([0.0, 1.0, 0.0, 0.0, 1.0], 0.50),
        discounted))
    self.assertTrue(np.array_equal(
        rollout_lib.discount(np.array([0.0, 1.0, 0.0, 0.0, 1.0]), 0.50),
        discounted))

  def testDiscountedAdvantageAndRewards(self):
    # lambda=1, No bootstrapping.
    values = [0.1, 0.5, 0.5, 0.25]
    (empirical_values,
     generalized_advantage) = rollout_lib.discounted_advantage_and_rewards(
         [0.0, 0.0, 0.0, 1.0],
         values,
         gamma=0.75,
         lambda_=1.0)
    expected_discounted_r = (
        np.array([1.0 * 0.75 ** n for n in range(3, -1, -1)]))
    expected_adv = expected_discounted_r - values
    self.assertTrue(np.array_equal(empirical_values, expected_discounted_r))
    self.assertTrue(np.allclose(generalized_advantage, expected_adv))

    # lambda=1, With bootstrapping.
    values = [0.1, 0.5, 0.5, 0.25, 0.75]
    (empirical_values,
     generalized_advantage) = rollout_lib.discounted_advantage_and_rewards(
         [0.0, 0.0, 0.0, 1.0],
         values,
         gamma=0.75,
         lambda_=1.0)
    expected_discounted_r = (
        np.array([0.75 * 0.75 ** n for n in range(4, 0, -1)])
        + np.array([1.0 * 0.75 ** n for n in range(3, -1, -1)]))
    expected_adv = expected_discounted_r - values[:-1]
    self.assertTrue(np.array_equal(empirical_values, expected_discounted_r))
    self.assertTrue(np.allclose(generalized_advantage, expected_adv))

    # lambda=0.5, With bootstrapping.
    values = [0.1, 0.5, 0.5, 0.25, 0.75]
    rewards = [0.0, 0.0, 0.0, 1.0]
    l = 0.5  # lambda
    g = 0.75  # gamma
    (empirical_values,
     generalized_advantage) = rollout_lib.discounted_advantage_and_rewards(
         rewards,
         values,
         gamma=g,
         lambda_=l)
    expected_discounted_r = (
        np.array([0.75 * g ** n for n in range(4, 0, -1)])
        + np.array([1.0 * g ** n for n in range(3, -1, -1)]))
    expected_adv = [0.0] * len(values)
    for t in range(3, -1, -1):
      delta_t = rewards[t] + g * values[t + 1] - values[t]
      expected_adv[t] = delta_t + g * l * expected_adv[t + 1]
    expected_adv = expected_adv[:-1]
    self.assertTrue(np.array_equal(empirical_values, expected_discounted_r))
    self.assertTrue(np.allclose(generalized_advantage, expected_adv))

  def testProcessRollouts(self):
    g = 0.95
    rollouts = [
        self.MakeRollout(
            states=[3, 6, 9],
            actions=[1, 2, 3],
            rewards=[1.0, -1.0, 0.5],
            values=[0.5, 0.5, 0.1]),
        self.MakeRollout(
            states=[10],
            actions=[5],
            rewards=[1.0],
            values=[0.5])]
    batch = rollout_lib.process_rollouts(rollouts, gamma=g)

    self.assertEqual(2, batch.batch_size)
    self.assertEqual(3, batch.max_time)
    self.assertEqual([3, 1], batch.episode_lengths)
    self.assertEqual([0.5, 1.0], batch.total_rewards)
    self.assertEqual(
        [[3, 6, 9], [10, 0, 0]],
        batch.states.tolist())
    self.assertEqual(
        [[1, 2, 3], [5, 0, 0]],
        batch.actions.tolist())

    rew1, rew2 = rollouts[0].rewards, rollouts[1].rewards
    expected_discounted_rewards = [
        [rew1[0] + g * rew1[1] + g * g * rew1[2],
         rew1[1] + g * rew1[2],
         rew1[2]],
        [rew2[0], 0.0, 0.0]]
    expected_advantages = [
        [dr - v
         for dr, v
         in zip(expected_discounted_rewards[0], rollouts[0].values)],
        [expected_discounted_rewards[1][0] - rollouts[1].values[0], 0.0, 0.0]]
    self.assertTrue(
        np.allclose(expected_discounted_rewards, batch.discounted_r))
    self.assertTrue(
        np.allclose(expected_advantages, batch.discounted_adv))


if __name__ == '__main__':
  tf.test.main()

#This file: bf_test.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Tests for common.bf."""

import tensorflow as tf

from common import bf  # brain coder


class BfTest(tf.test.TestCase):

  def assertCorrectOutput(self, target_output, eval_result):
    self.assertEqual(target_output, eval_result.output)
    self.assertTrue(eval_result.success)
    self.assertEqual(bf.Status.SUCCESS, eval_result.failure_reason)

  def testBasicOps(self):
    self.assertCorrectOutput(
        [3, 1, 2],
        bf.evaluate('+++.--.+.'))
    self.assertCorrectOutput(
        [1, 1, 2],
        bf.evaluate('+.<.>++.'))
    self.assertCorrectOutput(
        [0],
        bf.evaluate('+,.'))
    self.assertCorrectOutput(
        [ord(char) for char in 'Hello World!\n'],
        bf.evaluate(
            '>++++++++[-<+++++++++>]<.>>+>-[+]++>++>+++[>[->+++<<+++>]<<]>-----'
            '.>->+++..+++.>-.<<+[>[+>+]>>]<--------------.>>.+++.------.-------'
            '-.>+.>+.'))

  def testBase(self):
    self.assertCorrectOutput(
        [1, 4],
        bf.evaluate('+.--.', base=5, input_buffer=[]))

  def testInputBuffer(self):
    self.assertCorrectOutput(
        [2, 3, 4],
        bf.evaluate('>,[>,]<[.<]', input_buffer=[4, 3, 2]))

  def testBadChars(self):
    self.assertCorrectOutput(
        [2, 3, 4],
        bf.evaluate('>,[>,]hello<world[.<]comments',
                    input_buffer=[4, 3, 2]))

  def testUnmatchedBraces(self):
    self.assertCorrectOutput(
        [3, 6, 1],
        bf.evaluate('+++.]]]]>----.[[[[[>+.',
                    input_buffer=[],
                    base=10,
                    require_correct_syntax=False))

    eval_result = bf.evaluate(
        '+++.]]]]>----.[[[[[>+.',
        input_buffer=[],
        base=10,
        require_correct_syntax=True)
    self.assertEqual([], eval_result.output)
    self.assertFalse(eval_result.success)
    self.assertEqual(bf.Status.SYNTAX_ERROR,
                     eval_result.failure_reason)

  def testTimeout(self):
    er = bf.evaluate('+.[].', base=5, input_buffer=[], timeout=0.1)
    self.assertEqual(
        ([1], False, bf.Status.TIMEOUT),
        (er.output, er.success, er.failure_reason))
    self.assertTrue(0.07 < er.time < 0.21)

    er = bf.evaluate('+.[-].', base=5, input_buffer=[], timeout=0.1)
    self.assertEqual(
        ([1, 0], True, bf.Status.SUCCESS),
        (er.output, er.success, er.failure_reason))
    self.assertTrue(er.time < 0.15)

  def testMaxSteps(self):
    er = bf.evaluate('+.[].', base=5, input_buffer=[], timeout=None,
                     max_steps=100)
    self.assertEqual(
        ([1], False, bf.Status.STEP_LIMIT, 100),
        (er.output, er.success, er.failure_reason, er.steps))

    er = bf.evaluate('+.[-].', base=5, input_buffer=[], timeout=None,
                     max_steps=100)
    self.assertEqual(
        ([1, 0], True, bf.Status.SUCCESS),
        (er.output, er.success, er.failure_reason))
    self.assertTrue(er.steps < 100)

  def testOutputMemory(self):
    er = bf.evaluate('+>++>+++>++++.', base=256, input_buffer=[],
                     output_memory=True)
    self.assertEqual(
        ([4], True, bf.Status.SUCCESS),
        (er.output, er.success, er.failure_reason))
    self.assertEqual([1, 2, 3, 4], er.memory)

  def testProgramTrace(self):
    es = bf.ExecutionSnapshot
    er = bf.evaluate(',[.>,].', base=256, input_buffer=[2, 1], debug=True)
    self.assertEqual(
        [es(codeptr=0, codechar=',', memptr=0, memval=0, memory=[0],
            next_input=2, output_buffer=[]),
         es(codeptr=1, codechar='[', memptr=0, memval=2, memory=[2],
            next_input=1, output_buffer=[]),
         es(codeptr=2, codechar='.', memptr=0, memval=2, memory=[2],
            next_input=1, output_buffer=[]),
         es(codeptr=3, codechar='>', memptr=0, memval=2, memory=[2],
            next_input=1, output_buffer=[2]),
         es(codeptr=4, codechar=',', memptr=1, memval=0, memory=[2, 0],
            next_input=1, output_buffer=[2]),
         es(codeptr=5, codechar=']', memptr=1, memval=1, memory=[2, 1],
            next_input=0, output_buffer=[2]),
         es(codeptr=2, codechar='.', memptr=1, memval=1, memory=[2, 1],
            next_input=0, output_buffer=[2]),
         es(codeptr=3, codechar='>', memptr=1, memval=1, memory=[2, 1],
            next_input=0, output_buffer=[2, 1]),
         es(codeptr=4, codechar=',', memptr=2, memval=0, memory=[2, 1, 0],
            next_input=0, output_buffer=[2, 1]),
         es(codeptr=5, codechar=']', memptr=2, memval=0, memory=[2, 1, 0],
            next_input=0, output_buffer=[2, 1]),
         es(codeptr=6, codechar='.', memptr=2, memval=0, memory=[2, 1, 0],
            next_input=0, output_buffer=[2, 1]),
         es(codeptr=7, codechar='', memptr=2, memval=0, memory=[2, 1, 0],
            next_input=0, output_buffer=[2, 1, 0])],
        er.program_trace)


if __name__ == '__main__':
  tf.test.main()

#This file: config_lib_test.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Tests for common.config_lib."""

import tensorflow as tf

from common import config_lib  # brain coder


class ConfigLibTest(tf.test.TestCase):

  def testConfig(self):
    config = config_lib.Config(hello='world', foo='bar', num=123, f=56.7)
    self.assertEqual('world', config.hello)
    self.assertEqual('bar', config['foo'])
    config.hello = 'everyone'
    config['bar'] = 9000
    self.assertEqual('everyone', config['hello'])
    self.assertEqual(9000, config.bar)
    self.assertEqual(5, len(config))

  def testConfigUpdate(self):
    config = config_lib.Config(a=1, b=2, c=3)
    config.update({'b': 10, 'd': 4})
    self.assertEqual({'a': 1, 'b': 10, 'c': 3, 'd': 4}, config)

    config = config_lib.Config(a=1, b=2, c=3)
    config.update(b=10, d=4)
    self.assertEqual({'a': 1, 'b': 10, 'c': 3, 'd': 4}, config)

    config = config_lib.Config(a=1, b=2, c=3)
    config.update({'e': 5}, b=10, d=4)
    self.assertEqual({'a': 1, 'b': 10, 'c': 3, 'd': 4, 'e': 5}, config)

    config = config_lib.Config(
        a=1,
        b=2,
        x=config_lib.Config(
            l='a',
            y=config_lib.Config(m=1, n=2),
            z=config_lib.Config(
                q=config_lib.Config(a=10, b=20),
                r=config_lib.Config(s=1, t=2))))
    config.update(x={'y': {'m': 10}, 'z': {'r': {'s': 5}}})
    self.assertEqual(
        config_lib.Config(
            a=1, b=2,
            x=config_lib.Config(
                l='a',
                y=config_lib.Config(m=10, n=2),
                z=config_lib.Config(
                    q=config_lib.Config(a=10, b=20),
                    r=config_lib.Config(s=5, t=2)))),
        config)

    config = config_lib.Config(
        foo='bar',
        num=100,
        x=config_lib.Config(a=1, b=2, c=config_lib.Config(h=10, i=20, j=30)),
        y=config_lib.Config(qrs=5, tuv=10),
        d={'a': 1, 'b': 2},
        l=[1, 2, 3])
    config.update(
        config_lib.Config(
            foo='hat',
            num=50.5,
            x={'a': 5, 'z': -10},
            y=config_lib.Config(wxyz=-1)),
        d={'a': 10, 'c': 20},
        l=[3, 4, 5, 6])
    self.assertEqual(
        config_lib.Config(
            foo='hat',
            num=50.5,
            x=config_lib.Config(a=5, b=2, z=-10,
                                c=config_lib.Config(h=10, i=20, j=30)),
            y=config_lib.Config(qrs=5, tuv=10, wxyz=-1),
            d={'a': 10, 'c': 20},
            l=[3, 4, 5, 6]),
        config)
    self.assertTrue(isinstance(config.x, config_lib.Config))
    self.assertTrue(isinstance(config.x.c, config_lib.Config))
    self.assertTrue(isinstance(config.y, config_lib.Config))

    config = config_lib.Config(
        foo='bar',
        num=100,
        x=config_lib.Config(a=1, b=2, c=config_lib.Config(h=10, i=20, j=30)),
        y=config_lib.Config(qrs=5, tuv=10),
        d={'a': 1, 'b': 2},
        l=[1, 2, 3])
    config.update(
        config_lib.Config(
            foo=1234,
            num='hello',
            x={'a': 5, 'z': -10, 'c': {'h': -5, 'k': 40}},
            y=[1, 2, 3, 4],
            d='stuff',
            l={'a': 1, 'b': 2}))
    self.assertEqual(
        config_lib.Config(
            foo=1234,
            num='hello',
            x=config_lib.Config(a=5, b=2, z=-10,
                                c=config_lib.Config(h=-5, i=20, j=30, k=40)),
            y=[1, 2, 3, 4],
            d='stuff',
            l={'a': 1, 'b': 2}),
        config)
    self.assertTrue(isinstance(config.x, config_lib.Config))
    self.assertTrue(isinstance(config.x.c, config_lib.Config))
    self.assertTrue(isinstance(config.y, list))

  def testConfigStrictUpdate(self):
    config = config_lib.Config(a=1, b=2, c=3)
    config.strict_update({'b': 10, 'c': 20})
    self.assertEqual({'a': 1, 'b': 10, 'c': 20}, config)

    config = config_lib.Config(a=1, b=2, c=3)
    config.strict_update(b=10, c=20)
    self.assertEqual({'a': 1, 'b': 10, 'c': 20}, config)

    config = config_lib.Config(a=1, b=2, c=3, d=4)
    config.strict_update({'d': 100}, b=10, a=20)
    self.assertEqual({'a': 20, 'b': 10, 'c': 3, 'd': 100}, config)

    config = config_lib.Config(
        a=1,
        b=2,
        x=config_lib.Config(
            l='a',
            y=config_lib.Config(m=1, n=2),
            z=config_lib.Config(
                q=config_lib.Config(a=10, b=20),
                r=config_lib.Config(s=1, t=2))))
    config.strict_update(x={'y': {'m': 10}, 'z': {'r': {'s': 5}}})
    self.assertEqual(
        config_lib.Config(
            a=1, b=2,
            x=config_lib.Config(
                l='a',
                y=config_lib.Config(m=10, n=2),
                z=config_lib.Config(
                    q=config_lib.Config(a=10, b=20),
                    r=config_lib.Config(s=5, t=2)))),
        config)

    config = config_lib.Config(
        foo='bar',
        num=100,
        x=config_lib.Config(a=1, b=2, c=config_lib.Config(h=10, i=20, j=30)),
        y=config_lib.Config(qrs=5, tuv=10),
        d={'a': 1, 'b': 2},
        l=[1, 2, 3])
    config.strict_update(
        config_lib.Config(
            foo='hat',
            num=50,
            x={'a': 5, 'c': {'h': 100}},
            y=config_lib.Config(tuv=-1)),
        d={'a': 10, 'c': 20},
        l=[3, 4, 5, 6])
    self.assertEqual(
        config_lib.Config(
            foo='hat',
            num=50,
            x=config_lib.Config(a=5, b=2,
                                c=config_lib.Config(h=100, i=20, j=30)),
            y=config_lib.Config(qrs=5, tuv=-1),
            d={'a': 10, 'c': 20},
            l=[3, 4, 5, 6]),
        config)

  def testConfigStrictUpdateFail(self):
    config = config_lib.Config(a=1, b=2, c=3, x=config_lib.Config(a=1, b=2))
    with self.assertRaises(KeyError):
      config.strict_update({'b': 10, 'c': 20, 'd': 50})
    with self.assertRaises(KeyError):
      config.strict_update(b=10, d=50)
    with self.assertRaises(KeyError):
      config.strict_update(x={'c': 3})
    with self.assertRaises(TypeError):
      config.strict_update(a='string')
    with self.assertRaises(TypeError):
      config.strict_update(x={'a': 'string'})
    with self.assertRaises(TypeError):
      config.strict_update(x=[1, 2, 3])

  def testConfigFromStr(self):
    config = config_lib.Config.from_str("{'c': {'d': 5}, 'b': 2, 'a': 1}")
    self.assertEqual(
        {'c': {'d': 5}, 'b': 2, 'a': 1}, config)
    self.assertTrue(isinstance(config, config_lib.Config))
    self.assertTrue(isinstance(config.c, config_lib.Config))

  def testConfigParse(self):
    config = config_lib.Config.parse(
        'hello="world",num=1234.5,lst=[10,20.5,True,"hi",("a","b","c")],'
        'dct={9:10,"stuff":"qwerty","subdict":{1:True,2:False}},'
        'subconfig=c(a=1,b=[1,2,[3,4]],c=c(f="f",g="g"))')
    self.assertEqual(
        {'hello': 'world', 'num': 1234.5,
         'lst': [10, 20.5, True, 'hi', ('a', 'b', 'c')],
         'dct': {9: 10, 'stuff': 'qwerty', 'subdict': {1: True, 2: False}},
         'subconfig': {'a': 1, 'b': [1, 2, [3, 4]], 'c': {'f': 'f', 'g': 'g'}}},
        config)
    self.assertTrue(isinstance(config, config_lib.Config))
    self.assertTrue(isinstance(config.subconfig, config_lib.Config))
    self.assertTrue(isinstance(config.subconfig.c, config_lib.Config))
    self.assertFalse(isinstance(config.dct, config_lib.Config))
    self.assertFalse(isinstance(config.dct['subdict'], config_lib.Config))
    self.assertTrue(isinstance(config.lst[4], tuple))

  def testConfigParseErrors(self):
    with self.assertRaises(SyntaxError):
      config_lib.Config.parse('a=[1,2,b="hello"')
    with self.assertRaises(SyntaxError):
      config_lib.Config.parse('a=1,b=c(x="a",y="b"')
    with self.assertRaises(SyntaxError):
      config_lib.Config.parse('a=1,b=c(x="a")y="b"')
    with self.assertRaises(SyntaxError):
      config_lib.Config.parse('a=1,b=c(x="a"),y="b",')

  def testOneOf(self):
    def make_config():
      return config_lib.Config(
          data=config_lib.OneOf(
              [config_lib.Config(task=1, a='hello'),
               config_lib.Config(task=2, a='world', b='stuff'),
               config_lib.Config(task=3, c=1234)],
              task=2),
          model=config_lib.Config(stuff=1))

    config = make_config()
    config.update(config_lib.Config.parse(
        'model=c(stuff=2),data=c(task=1,a="hi")'))
    self.assertEqual(
        config_lib.Config(
            data=config_lib.Config(task=1, a='hi'),
            model=config_lib.Config(stuff=2)),
        config)

    config = make_config()
    config.update(config_lib.Config.parse(
        'model=c(stuff=2),data=c(task=2,a="hi")'))
    self.assertEqual(
        config_lib.Config(
            data=config_lib.Config(task=2, a='hi', b='stuff'),
            model=config_lib.Config(stuff=2)),
        config)

    config = make_config()
    config.update(config_lib.Config.parse(
        'model=c(stuff=2),data=c(task=3)'))
    self.assertEqual(
        config_lib.Config(
            data=config_lib.Config(task=3, c=1234),
            model=config_lib.Config(stuff=2)),
        config)

    config = make_config()
    config.update(config_lib.Config.parse(
        'model=c(stuff=2)'))
    self.assertEqual(
        config_lib.Config(
            data=config_lib.Config(task=2, a='world', b='stuff'),
            model=config_lib.Config(stuff=2)),
        config)

    config = make_config()
    config.update(config_lib.Config.parse(
        'model=c(stuff=2),data=c(task=4,d=9999)'))
    self.assertEqual(
        config_lib.Config(
            data=config_lib.Config(task=4, d=9999),
            model=config_lib.Config(stuff=2)),
        config)

    config = make_config()
    config.update(config_lib.Config.parse(
        'model=c(stuff=2),data=5'))
    self.assertEqual(
        config_lib.Config(
            data=5,
            model=config_lib.Config(stuff=2)),
        config)

  def testOneOfStrict(self):
    def make_config():
      return config_lib.Config(
          data=config_lib.OneOf(
              [config_lib.Config(task=1, a='hello'),
               config_lib.Config(task=2, a='world', b='stuff'),
               config_lib.Config(task=3, c=1234)],
              task=2),
          model=config_lib.Config(stuff=1))

    config = make_config()
    config.strict_update(config_lib.Config.parse(
        'model=c(stuff=2),data=c(task=1,a="hi")'))
    self.assertEqual(
        config_lib.Config(
            data=config_lib.Config(task=1, a='hi'),
            model=config_lib.Config(stuff=2)),
        config)

    config = make_config()
    config.strict_update(config_lib.Config.parse(
        'model=c(stuff=2),data=c(task=2,a="hi")'))
    self.assertEqual(
        config_lib.Config(
            data=config_lib.Config(task=2, a='hi', b='stuff'),
            model=config_lib.Config(stuff=2)),
        config)

    config = make_config()
    config.strict_update(config_lib.Config.parse(
        'model=c(stuff=2),data=c(task=3)'))
    self.assertEqual(
        config_lib.Config(
            data=config_lib.Config(task=3, c=1234),
            model=config_lib.Config(stuff=2)),
        config)

    config = make_config()
    config.strict_update(config_lib.Config.parse(
        'model=c(stuff=2)'))
    self.assertEqual(
        config_lib.Config(
            data=config_lib.Config(task=2, a='world', b='stuff'),
            model=config_lib.Config(stuff=2)),
        config)

  def testNestedOneOf(self):
    def make_config():
      return config_lib.Config(
          data=config_lib.OneOf(
              [config_lib.Config(task=1, a='hello'),
               config_lib.Config(
                   task=2,
                   a=config_lib.OneOf(
                       [config_lib.Config(x=1, y=2),
                        config_lib.Config(x=-1, y=1000, z=4)],
                       x=1)),
               config_lib.Config(task=3, c=1234)],
              task=2),
          model=config_lib.Config(stuff=1))

    config = make_config()
    config.update(config_lib.Config.parse(
        'model=c(stuff=2),data=c(task=2,a=c(x=-1,z=8))'))
    self.assertEqual(
        config_lib.Config(
            data=config_lib.Config(
                task=2,
                a=config_lib.Config(x=-1, y=1000, z=8)),
            model=config_lib.Config(stuff=2)),
        config)

    config = make_config()
    config.strict_update(config_lib.Config.parse(
        'model=c(stuff=2),data=c(task=2,a=c(x=-1,z=8))'))
    self.assertEqual(
        config_lib.Config(
            data=config_lib.Config(
                task=2,
                a=config_lib.Config(x=-1, y=1000, z=8)),
            model=config_lib.Config(stuff=2)),
        config)

    config = make_config()
    config.update(config_lib.Config.parse('model=c(stuff=2)'))
    self.assertEqual(
        config_lib.Config(
            data=config_lib.Config(
                task=2,
                a=config_lib.Config(x=1, y=2)),
            model=config_lib.Config(stuff=2)),
        config)

    config = make_config()
    config.strict_update(config_lib.Config.parse('model=c(stuff=2)'))
    self.assertEqual(
        config_lib.Config(
            data=config_lib.Config(
                task=2,
                a=config_lib.Config(x=1, y=2)),
            model=config_lib.Config(stuff=2)),
        config)

  def testOneOfStrictErrors(self):
    def make_config():
      return config_lib.Config(
          data=config_lib.OneOf(
              [config_lib.Config(task=1, a='hello'),
               config_lib.Config(task=2, a='world', b='stuff'),
               config_lib.Config(task=3, c=1234)],
              task=2),
          model=config_lib.Config(stuff=1))

    config = make_config()
    with self.assertRaises(TypeError):
      config.strict_update(config_lib.Config.parse(
          'model=c(stuff=2),data=[1,2,3]'))

    config = make_config()
    with self.assertRaises(KeyError):
      config.strict_update(config_lib.Config.parse(
          'model=c(stuff=2),data=c(task=3,c=5678,d=9999)'))

    config = make_config()
    with self.assertRaises(ValueError):
      config.strict_update(config_lib.Config.parse(
          'model=c(stuff=2),data=c(task=4,d=9999)'))

    config = make_config()
    with self.assertRaises(TypeError):
      config.strict_update(config_lib.Config.parse(
          'model=c(stuff=2),data=5'))


if __name__ == '__main__':
  tf.test.main()

#This file: reward.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Reward functions, distance functions, and reward managers."""

from abc import ABCMeta
from abc import abstractmethod
from math import log


# All sequences here are assumed to be lists of ints bounded
# between 0 and `base`-1 (inclusive).


#################################
### Scalar Distance Functions ###
#################################


def abs_diff(a, b, base=0):
  """Absolute value of difference between scalars.

  abs_diff is symmetric, i.e. `a` and `b` are interchangeable.

  Args:
    a: First argument. An int.
    b: Seconds argument. An int.
    base: Dummy argument so that the argument signature matches other scalar
        diff functions. abs_diff is the same in all bases.

  Returns:
    abs(a - b).
  """
  del base  # Unused.
  return abs(a - b)


def mod_abs_diff(a, b, base):
  """Shortest distance between `a` and `b` in the modular integers base `base`.

  The smallest distance between a and b is returned.
  Example: mod_abs_diff(1, 99, 100) ==> 2. It is not 98.

  mod_abs_diff is symmetric, i.e. `a` and `b` are interchangeable.

  Args:
    a: First argument. An int.
    b: Seconds argument. An int.
    base: The modulo base. A positive int.

  Returns:
    Shortest distance.
  """
  diff = abs(a - b)
  if diff >= base:
    diff %= base
  return min(diff, (-diff) + base)


###############################
### List Distance Functions ###
###############################


def absolute_distance(pred, target, base, scalar_diff_fn=abs_diff):
  """Asymmetric list distance function.

  List distance is the sum of element-wise distances, like Hamming distance, but
  where `pred` can be longer or shorter than `target`. For each position in both
  `pred` and `target`, distance between those elements is computed with
  `scalar_diff_fn`. For missing or extra elements in `pred`, the maximum
  distance is assigned, which is equal to `base`.

  Distance is 0 when `pred` and `target` are identical, and will be a positive
  integer when they are not.

  Args:
    pred: Prediction list. Distance from this list is computed.
    target: Target list. Distance to this list is computed.
    base: The integer base to use. For example, a list of chars would use base
        256.
    scalar_diff_fn: Element-wise distance function.

  Returns:
    List distance between `pred` and `target`.
  """
  d = 0
  for i, target_t in enumerate(target):
    if i >= len(pred):
      d += base  # A missing slot is worth the max distance.
    else:
      # Add element-wise distance for this slot.
      d += scalar_diff_fn(pred[i], target_t, base)
  if len(pred) > len(target):
    # Each extra slot is worth the max distance.
    d += (len(pred) - len(target)) * base
  return d


def log_absolute_distance(pred, target, base):
  """Asymmetric list distance function that uses log distance.

  A list distance which computes sum of element-wise distances, similar to
  `absolute_distance`. Unlike `absolute_distance`, this scales the resulting
  distance to be a float.

  Element-wise distance are log-scale. Distance between two list changes
  relatively less for elements that are far apart, but changes a lot (goes to 0
  faster) when values get close together.

  Args:
    pred: List of ints. Computes distance from this list to the target.
    target: List of ints. This is the "correct" list which the prediction list
        is trying to match.
    base: Integer base.

  Returns:
    Float distance normalized so that when `pred` is at most as long as `target`
    the distance is between 0.0 and 1.0. Distance grows unboundedly large
    as `pred` grows past `target` in length.
  """
  if not target:
    length_normalizer = 1.0
    if not pred:
      # Distance between [] and [] is 0.0 since they are equal.
      return 0.0
  else:
    length_normalizer = float(len(target))
  # max_dist is the maximum element-wise distance, before taking log and
  # scaling. Since we use `mod_abs_diff`, it would be (base // 2), but we add
  # 1 to it so that missing or extra positions get the maximum penalty.
  max_dist = base // 2 + 1

  # The log-distance will be scaled by a factor.
  # Note: +1 is added to the numerator and denominator to avoid log(0). This
  # only has a translational effect, i.e. log(dist + 1) / log(max_dist + 1).
  factor = log(max_dist + 1)

  d = 0.0  # Total distance to be computed.
  for i, target_t in enumerate(target):
    if i >= len(pred):
      # Assign the max element-wise distance for missing positions. This is 1.0
      # after scaling.
      d += 1.0
    else:
      # Add the log-dist divided by a scaling factor.
      d += log(mod_abs_diff(pred[i], target_t, base) + 1) / factor
  if len(pred) > len(target):
    # Add the max element-wise distance for each extra position.
    # Since max dist after scaling is 1, this is just the difference in list
    # lengths.
    d += (len(pred) - len(target))
  return d / length_normalizer  # Normalize again by the target length.


########################
### Reward Functions ###
########################

# Reward functions assign reward based on program output.
# Warning: only use these functions as the terminal rewards in episodes, i.e.
# for the "final" programs.


def absolute_distance_reward(pred, target, base, scalar_diff_fn=abs_diff):
  """Reward function based on absolute_distance function.

  Maximum reward, 1.0, is given when the lists are equal. Reward is scaled
  so that 0.0 reward is given when `pred` is the empty list (assuming `target`
  is not empty). Reward can go negative when `pred` is longer than `target`.

  This is an asymmetric reward function, so which list is the prediction and
  which is the target matters.

  Args:
    pred: Prediction sequence. This should be the sequence outputted by the
        generated code. List of ints n, where 0 <= n < base.
    target: Target sequence. The correct sequence that the generated code needs
        to output. List of ints n, where 0 <= n < base.
    base: Base of the computation.
    scalar_diff_fn: Element-wise distance function.

  Returns:
    Reward computed based on `pred` and `target`. A float.
  """
  unit_dist = float(base * len(target))
  if unit_dist == 0:
    unit_dist = base
  dist = absolute_distance(pred, target, base, scalar_diff_fn=scalar_diff_fn)
  return (unit_dist - dist) / unit_dist


def absolute_mod_distance_reward(pred, target, base):
  """Same as `absolute_distance_reward` but `mod_abs_diff` scalar diff is used.

  Args:
    pred: Prediction sequence. This should be the sequence outputted by the
        generated code. List of ints n, where 0 <= n < base.
    target: Target sequence. The correct sequence that the generated code needs
        to output. List of ints n, where 0 <= n < base.
    base: Base of the computation.

  Returns:
    Reward computed based on `pred` and `target`. A float.
  """
  return absolute_distance_reward(pred, target, base, mod_abs_diff)


def absolute_log_distance_reward(pred, target, base):
  """Compute reward using `log_absolute_distance`.

  Maximum reward, 1.0, is given when the lists are equal. Reward is scaled
  so that 0.0 reward is given when `pred` is the empty list (assuming `target`
  is not empty). Reward can go negative when `pred` is longer than `target`.

  This is an asymmetric reward function, so which list is the prediction and
  which is the target matters.

  This reward function has the nice property that much more reward is given
  for getting the correct value (at each position) than for there being any
  value at all. For example, in base 100, lets say pred = [1] * 1000
  and target = [10] * 1000. A lot of reward would be given for being 80%
  accurate (worst element-wise distance is 50, distances here are 9) using
  `absolute_distance`. `log_absolute_distance` on the other hand will give
  greater and greater reward increments the closer each predicted value gets to
  the target. That makes the reward given for accuracy somewhat independant of
  the base.

  Args:
    pred: Prediction sequence. This should be the sequence outputted by the
        generated code. List of ints n, where 0 <= n < base.
    target: Target sequence. The correct sequence that the generated code needs
        to output. List of ints n, where 0 <= n < base.
    base: Base of the computation.

  Returns:
    Reward computed based on `pred` and `target`. A float.
  """
  return 1.0 - log_absolute_distance(pred, target, base)


#######################
### Reward Managers ###
#######################

# Reward managers assign reward to many code attempts throughout an episode.


class RewardManager(object):
  """Reward managers administer reward across an episode.

  Reward managers are used for "editor" environments. These are environments
  where the agent has some way to edit its code over time, and run its code
  many time in the same episode, so that it can make incremental improvements.

  Reward managers are instantiated with a target sequence, which is the known
  correct program output. The manager is called on the output from a proposed
  code, and returns reward. If many proposal outputs are tried, reward may be
  some stateful function that takes previous tries into account. This is done,
  in part, so that an agent cannot accumulate unbounded reward just by trying
  junk programs as often as possible. So reward managers should not give the
  same reward twice if the next proposal is not better than the last.
  """
  __metaclass__ = ABCMeta

  def __init__(self, target, base, distance_fn=absolute_distance):
    self._target = list(target)
    self._base = base
    self._distance_fn = distance_fn

  @abstractmethod
  def __call__(self, sequence):
    """Call this reward manager like a function to get reward.

    Calls to reward manager are stateful, and will take previous sequences
    into account. Repeated calls with the same sequence may produce different
    rewards.

    Args:
      sequence: List of integers (each between 0 and base - 1). This is the
          proposal sequence. Reward will be computed based on the distance
          from this sequence to the target (distance function and target are
          given in the constructor), as well as previous sequences tried during
          the lifetime of this object.

    Returns:
      Float value. The reward received from this call.
    """
    return 0.0


class DeltaRewardManager(RewardManager):
  """Simple reward manager that assigns reward for the net change in distance.

  Given some (possibly asymmetric) list distance function, gives reward for
  relative changes in prediction distance to the target.

  For example, if on the first call the distance is 3.0, the change in distance
  is -3 (from starting distance of 0). That relative change will be scaled to
  produce a negative reward for this step. On the next call, the distance is 2.0
  which is a +1 change, and that will be scaled to give a positive reward.
  If the final call has distance 0 (the target is achieved), that is another
  positive change of +2. The total reward across all 3 calls is then 0, which is
  the highest posible episode total.

  Reward is scaled so that the maximum element-wise distance is worth 1.0.
  Maximum total episode reward attainable is 0.
  """

  def __init__(self, target, base, distance_fn=absolute_distance):
    super(DeltaRewardManager, self).__init__(target, base, distance_fn)
    self._last_diff = 0

  def _diff(self, seq):
    return self._distance_fn(seq, self._target, self._base)

  def _delta_reward(self, seq):
    # Reward is relative to previous sequence diff.
    # Reward is scaled so that maximum token difference is worth 1.0.
    # Reward = (last_diff - this_diff) / self.base.
    # Reward is positive if this sequence is closer to the target than the
    # previous sequence, and negative if this sequence is further away.
    diff = self._diff(seq)
    reward = (self._last_diff - diff) / float(self._base)
    self._last_diff = diff
    return reward

  def __call__(self, seq):
    return self._delta_reward(seq)


class FloorRewardManager(RewardManager):
  """Assigns positive reward for each step taken closer to the target.

  Given some (possibly asymmetric) list distance function, gives reward for
  whenever a new episode minimum distance is reached. No reward is given if
  the distance regresses to a higher value, so that the sum of rewards
  for the episode is positive.

  Reward is scaled so that the maximum element-wise distance is worth 1.0.
  Maximum total episode reward attainable is len(target).

  If the prediction sequence is longer than the target, a reward of -1 is given.
  Subsequence predictions which are also longer get 0 reward. The -1 penalty
  will be canceled out with a +1 reward when a prediction is given which is at
  most the length of the target.
  """

  def __init__(self, target, base, distance_fn=absolute_distance):
    super(FloorRewardManager, self).__init__(target, base, distance_fn)
    self._last_diff = 0
    self._min_diff = self._max_diff()
    self._too_long_penality_given = False

  def _max_diff(self):
    return self._distance_fn([], self._target, self._base)

  def _diff(self, seq):
    return self._distance_fn(seq, self._target, self._base)

  def _delta_reward(self, seq):
    # Reward is only given if this sequence is closer to the target than any
    # previous sequence.
    # Reward is scaled so that maximum token difference is worth 1.0
    # Reward = (min_diff - this_diff) / self.base
    # Reward is always positive.
    diff = self._diff(seq)
    if diff < self._min_diff:
      reward = (self._min_diff - diff) / float(self._base)
      self._min_diff = diff
    else:
      reward = 0.0
    return reward

  def __call__(self, seq):
    if len(seq) > len(self._target):  # Output is too long.
      if not self._too_long_penality_given:
        self._too_long_penality_given = True
        reward = -1.0
      else:
        reward = 0.0  # Don't give this penalty more than once.
      return reward

    reward = self._delta_reward(seq)
    if self._too_long_penality_given:
      reward += 1.0  # Return the subtracted reward.
      self._too_long_penality_given = False
    return reward


#This file: schedules.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Schedule functions for controlling hparams over time."""

from abc import ABCMeta
from abc import abstractmethod
import math

from common import config_lib  # brain coder


class Schedule(object):
  """Schedule is a function which sets a hyperparameter's value over time.

  For example, a schedule can be used to decay an hparams, or oscillate it over
  time.

  This object is constructed with an instance of config_lib.Config (will be
  specific to each class implementation). For example if this is a decay
  schedule, the config may specify the rate of decay and decay start time. Then
  the object instance is called like a function, mapping global step (an integer
  counting how many calls to the train op have been made) to the hparam value.

  Properties of a schedule function f(t):
  0) Domain of t is the non-negative integers (t may be 0).
  1) Range of f is the reals.
  2) Schedule functions can assume that they will be called in time order. This
     allows schedules to be stateful.
  3) Schedule functions should be deterministic. Two schedule instances with the
     same config must always give the same value for each t, and regardless of
     what t's it was previously called on. Users may call f(t) on arbitrary
     (positive) time jumps. Essentially, multiple schedule instances used in
     replica training will behave the same.
  4) Duplicate successive calls on the same time are allowed.
  """
  __metaclass__ = ABCMeta

  @abstractmethod
  def __init__(self, config):
    """Construct this schedule with a config specific to each class impl.

    Args:
      config: An instance of config_lib.Config.
    """
    pass

  @abstractmethod
  def __call__(self, global_step):
    """Map `global_step` to a value.

    `global_step` is an integer counting how many calls to the train op have
    been made across all replicas (hence why it is global). Implementations
    may assume calls to be made in time order, i.e. `global_step` now >=
    previous `global_step` values.

    Args:
      global_step: Non-negative integer.

    Returns:
      Hparam value at this step. A number.
    """
    pass


class ConstSchedule(Schedule):
  """Constant function.

  config:
    const: Constant value at every step.

  f(t) = const.
  """

  def __init__(self, config):
    super(ConstSchedule, self).__init__(config)
    self.const = config.const

  def __call__(self, global_step):
    return self.const


class LinearDecaySchedule(Schedule):
  """Linear decay function.

  config:
    initial: Decay starts from this value.
    final: Decay ends at this value.
    start_time: Step when decay starts. Constant before it.
    end_time: When decay ends. Constant after it.

  f(t) is a linear function when start_time <= t <= end_time, with slope of
  (final - initial) / (end_time - start_time). f(t) = initial
  when t <= start_time. f(t) = final when t >= end_time.

  If start_time == end_time, this becomes a step function.
  """

  def __init__(self, config):
    super(LinearDecaySchedule, self).__init__(config)
    self.initial = config.initial
    self.final = config.final
    self.start_time = config.start_time
    self.end_time = config.end_time

    if self.end_time < self.start_time:
      raise ValueError('start_time must be before end_time.')

    # Linear interpolation.
    self._time_diff = float(self.end_time - self.start_time)
    self._diff = float(self.final - self.initial)
    self._slope = (
        self._diff / self._time_diff if self._time_diff > 0 else float('inf'))

  def __call__(self, global_step):
    if global_step <= self.start_time:
      return self.initial
    if global_step > self.end_time:
      return self.final
    return self.initial + (global_step - self.start_time) * self._slope


class ExponentialDecaySchedule(Schedule):
  """Exponential decay function.

  See https://en.wikipedia.org/wiki/Exponential_decay.

  Use this decay function to decay over orders of magnitude. For example, to
  decay learning rate from 1e-2 to 1e-6. Exponential decay will decay the
  exponent linearly.

  config:
    initial: Decay starts from this value.
    final: Decay ends at this value.
    start_time: Step when decay starts. Constant before it.
    end_time: When decay ends. Constant after it.

  f(t) is an exponential decay function when start_time <= t <= end_time. The
  decay rate and amplitude are chosen so that f(t) = initial when
  t = start_time, and f(t) = final when t = end_time. f(t) is constant for
  t < start_time or t > end_time. initial and final must be positive values.

  If start_time == end_time, this becomes a step function.
  """

  def __init__(self, config):
    super(ExponentialDecaySchedule, self).__init__(config)
    self.initial = config.initial
    self.final = config.final
    self.start_time = config.start_time
    self.end_time = config.end_time

    if self.initial <= 0 or self.final <= 0:
      raise ValueError('initial and final must be positive numbers.')

    # Linear interpolation in log space.
    self._linear_fn = LinearDecaySchedule(
        config_lib.Config(
            initial=math.log(self.initial),
            final=math.log(self.final),
            start_time=self.start_time,
            end_time=self.end_time))

  def __call__(self, global_step):
    return math.exp(self._linear_fn(global_step))


class SmootherstepDecaySchedule(Schedule):
  """Smootherstep decay function.

  A sigmoidal like transition from initial to final values. A smoother
  transition than linear and exponential decays, hence the name.
  See https://en.wikipedia.org/wiki/Smoothstep.

  config:
    initial: Decay starts from this value.
    final: Decay ends at this value.
    start_time: Step when decay starts. Constant before it.
    end_time: When decay ends. Constant after it.

  f(t) is fully defined here:
  https://en.wikipedia.org/wiki/Smoothstep#Variations.

  f(t) is smooth, as in its first-derivative exists everywhere.
  """

  def __init__(self, config):
    super(SmootherstepDecaySchedule, self).__init__(config)
    self.initial = config.initial
    self.final = config.final
    self.start_time = config.start_time
    self.end_time = config.end_time

    if self.end_time < self.start_time:
      raise ValueError('start_time must be before end_time.')

    self._time_diff = float(self.end_time - self.start_time)
    self._diff = float(self.final - self.initial)

  def __call__(self, global_step):
    if global_step <= self.start_time:
      return self.initial
    if global_step > self.end_time:
      return self.final
    x = (global_step - self.start_time) / self._time_diff

    # Smootherstep
    return self.initial + x * x * x * (x * (x * 6 - 15) + 10) * self._diff


class HardOscillatorSchedule(Schedule):
  """Hard oscillator function.

  config:
    high: Max value of the oscillator. Value at constant plateaus.
    low: Min value of the oscillator. Value at constant valleys.
    start_time: Global step when oscillation starts. Constant before this.
    period: Width of one oscillation, i.e. number of steps over which the
        oscillation takes place.
    transition_fraction: Fraction of the period spent transitioning between high
        and low values. 50% of this time is spent rising, and 50% of this time
        is spent falling. 50% of the remaining time is spent constant at the
        high value, and 50% of the remaining time is spent constant at the low
        value. transition_fraction = 1.0 means the entire period is spent
        rising and falling. transition_fraction = 0.0 means no time is spent
        rising and falling, i.e. the function jumps instantaneously between
        high and low.

  f(t) = high when t < start_time.
  f(t) is periodic when t >= start_time, with f(t + period) = f(t).
  f(t) is linear with positive slope when rising, and negative slope when
  falling. At the start of the period t0, f(t0) = high and begins to descend.
  At the middle of the period f is low and is constant until the ascension
  begins. f then rises from low to high and is constant again until the period
  repeats.

  Note: when transition_fraction is 0, f starts the period low and ends high.
  """

  def __init__(self, config):
    super(HardOscillatorSchedule, self).__init__(config)
    self.high = config.high
    self.low = config.low
    self.start_time = config.start_time
    self.period = float(config.period)
    self.transition_fraction = config.transition_fraction
    self.half_transition_fraction = config.transition_fraction / 2.0

    if self.transition_fraction < 0 or self.transition_fraction > 1.0:
      raise ValueError('transition_fraction must be between 0 and 1.0')
    if self.period <= 0:
      raise ValueError('period must be positive')

    self._slope = (
        float(self.high - self.low) / self.half_transition_fraction
        if self.half_transition_fraction > 0 else float('inf'))

  def __call__(self, global_step):
    if global_step < self.start_time:
      return self.high
    period_pos = ((global_step - self.start_time) / self.period) % 1.0
    if period_pos >= 0.5:
      # ascending
      period_pos -= 0.5
      if period_pos < self.half_transition_fraction:
        return self.low + period_pos * self._slope
      else:
        return self.high
    else:
      # descending
      if period_pos < self.half_transition_fraction:
        return self.high - period_pos * self._slope
      else:
        return self.low


_NAME_TO_CONFIG = {
    'const': ConstSchedule,
    'linear_decay': LinearDecaySchedule,
    'exp_decay': ExponentialDecaySchedule,
    'smooth_decay': SmootherstepDecaySchedule,
    'hard_osc': HardOscillatorSchedule,
}


def make_schedule(config):
  """Schedule factory.

  Given `config` containing a `fn` property, a Schedule implementation is
  instantiated with `config`. See `_NAME_TO_CONFIG` for `fn` options.

  Args:
    config: Config with a `fn` option that specifies which Schedule
        implementation to use. `config` is passed into the constructor.

  Returns:
    A Schedule impl instance.
  """
  schedule_class = _NAME_TO_CONFIG[config.fn]
  return schedule_class(config)

#This file: ga_train_test.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Tests for ga_train.

Tests that ga runs for a few generations without crashing.
"""

from absl import flags
import tensorflow as tf

from single_task import defaults  # brain coder
from single_task import run  # brain coder

FLAGS = flags.FLAGS


class GaTest(tf.test.TestCase):

  def RunTrainingSteps(self, config_string, num_steps=10):
    """Run a few training steps with the given config.

    Just check that nothing crashes.

    Args:
      config_string: Config encoded in a string. See
          $REPO_PATH/common/config_lib.py
      num_steps: Number of training steps to run. Defaults to 10.
    """
    config = defaults.default_config_with_updates(config_string)
    FLAGS.max_npe = num_steps * config.batch_size
    FLAGS.logdir = tf.test.get_temp_dir()
    FLAGS.config = config_string
    run.main(None)

  def testGeneticAlgorithm(self):
    self.RunTrainingSteps(
        'env=c(task="reverse"),'
        'agent=c(algorithm="ga"),'
        'timestep_limit=40,batch_size=64')

  def testUniformRandomSearch(self):
    self.RunTrainingSteps(
        'env=c(task="reverse"),'
        'agent=c(algorithm="rand"),'
        'timestep_limit=40,batch_size=64')


if __name__ == '__main__':
  tf.test.main()

#This file: misc.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Utilities specific to this project."""

from collections import namedtuple
from six import string_types


#####################
# BF-lang utilities #
#####################


BF_EOS_INT = 0  # Also used as SOS (start of sequence).
BF_EOS_CHAR = TEXT_EOS_CHAR = '_'
BF_LANG_INTS = range(1, 9)
BF_INT_TO_CHAR = [BF_EOS_CHAR, '>', '<', '+', '-', '[', ']', '.', ',']
BF_CHAR_TO_INT = dict([(c, i) for i, c in enumerate(BF_INT_TO_CHAR)])


RewardInfo = namedtuple('RewardInfo', ['episode_rewards', 'input_case',
                                       'correct_output',
                                       'code_output', 'reason', 'input_type',
                                       'output_type'])


class IOType(object):
  string = 'string'
  integer = 'integer'
  boolean = 'boolean'


class IOTuple(tuple):
  pass


def flatten(lst):
  return [item for row in lst for item in row]


def bf_num_tokens():
  # BF tokens plus EOS.
  return len(BF_INT_TO_CHAR)


def bf_char2int(bf_char):
  """Convert BF code char to int token."""
  return BF_CHAR_TO_INT[bf_char]


def bf_int2char(bf_int):
  """Convert BF int token to code char."""
  return BF_INT_TO_CHAR[bf_int]


def bf_tokens_to_string(bf_tokens, truncate=True):
  """Convert token list to code string. Will truncate at EOS token.

  Args:
    bf_tokens: Python list of ints representing the code string.
    truncate: If true, the output string will end at the first EOS token.
        If false, the entire token list is converted to string.

  Returns:
    String representation of the tokens.

  Raises:
    ValueError: If bf_tokens is not a python list.
  """
  if not isinstance(bf_tokens, list):
    raise ValueError('Only python list supported here.')
  if truncate:
    try:
      eos_index = bf_tokens.index(BF_EOS_INT)
    except ValueError:
      eos_index = len(bf_tokens)
  else:
    eos_index = len(bf_tokens)
  return ''.join([BF_INT_TO_CHAR[t] for t in bf_tokens[:eos_index]])


def bf_string_to_tokens(bf_string):
  """Convert string to token list. Will strip and append EOS token."""
  tokens = [BF_CHAR_TO_INT[char] for char in bf_string.strip()]
  tokens.append(BF_EOS_INT)
  return tokens


def tokens_to_text(tokens):
  """Convert token list to human readable text."""
  return ''.join(
      [TEXT_EOS_CHAR if t == 0 else chr(t - 1 + ord('A')) for t in tokens])


###################################
# Number representation utilities #
###################################


# https://en.wikipedia.org/wiki/Metric_prefix
si_magnitudes = {
    'k': 1e3,
    'm': 1e6,
    'g': 1e9}


def si_to_int(s):
  """Convert string ending with SI magnitude to int.

  Examples: 5K ==> 5000, 12M ==> 12000000.

  Args:
    s: String in the form 'xx..xP' where x is a digit and P is an SI prefix.

  Returns:
    Integer equivalent to the string.
  """
  if isinstance(s, string_types) and s[-1].lower() in si_magnitudes.keys():
    return int(int(s[:-1]) * si_magnitudes[s[-1].lower()])
  return int(s)


def int_to_si(n):
  """Convert integer to string with SI magnitude.

  `n` will be truncated.

  Examples: 5432 ==> 5k, 12345678 ==> 12M

  Args:
    n: Integer to represent as a string.

  Returns:
    String representation of `n` containing SI magnitude.
  """
  m = abs(n)
  sign = -1 if n < 0 else 1
  if m < 1e3:
    return str(n)
  if m < 1e6:
    return '{0}K'.format(sign*int(m / 1e3))
  if m < 1e9:
    return '{0}M'.format(sign*int(m / 1e6))
  if m < 1e12:
    return '{0}G'.format(sign*int(m / 1e9))
  return str(m)


#This file: run.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

r"""Run training.

Choose training algorithm and task(s) and follow these examples.

Run synchronous policy gradient training locally:

CONFIG="agent=c(algorithm='pg'),env=c(task='reverse')"
OUT_DIR="/tmp/bf_pg_local"
rm -rf $OUT_DIR
bazel run -c opt single_task:run -- \
    --alsologtostderr \
    --config="$CONFIG" \
    --max_npe=0 \
    --logdir="$OUT_DIR" \
    --summary_interval=1 \
    --model_v=0
learning/brain/tensorboard/tensorboard.sh --port 12345 --logdir "$OUT_DIR"


Run genetic algorithm locally:

CONFIG="agent=c(algorithm='ga'),env=c(task='reverse')"
OUT_DIR="/tmp/bf_ga_local"
rm -rf $OUT_DIR
bazel run -c opt single_task:run -- \
    --alsologtostderr \
    --config="$CONFIG" \
    --max_npe=0 \
    --logdir="$OUT_DIR"


Run uniform random search locally:

CONFIG="agent=c(algorithm='rand'),env=c(task='reverse')"
OUT_DIR="/tmp/bf_rand_local"
rm -rf $OUT_DIR
bazel run -c opt single_task:run -- \
    --alsologtostderr \
    --config="$CONFIG" \
    --max_npe=0 \
    --logdir="$OUT_DIR"
"""

from absl import app
from absl import flags
from absl import logging

from single_task import defaults  # brain coder
from single_task import ga_train  # brain coder
from single_task import pg_train  # brain coder

FLAGS = flags.FLAGS
flags.DEFINE_string('config', '', 'Configuration.')
flags.DEFINE_string(
    'logdir', None, 'Absolute path where to write results.')
flags.DEFINE_integer('task_id', 0, 'ID for this worker.')
flags.DEFINE_integer('num_workers', 1, 'How many workers there are.')
flags.DEFINE_integer(
    'max_npe', 0,
    'NPE = number of programs executed. Maximum number of programs to execute '
    'in each run. Training will complete when this threshold is reached. Set '
    'to 0 for unlimited training.')
flags.DEFINE_integer(
    'num_repetitions', 1,
    'Number of times the same experiment will be run (globally across all '
    'workers). Each run is independent.')
flags.DEFINE_string(
    'log_level', 'INFO',
    'The threshold for what messages will be logged. One of DEBUG, INFO, WARN, '
    'ERROR, or FATAL.')


# To register an algorithm:
# 1) Add dependency in the BUILD file to this build rule.
# 2) Import the algorithm's module at the top of this file.
# 3) Add a new entry in the following dict. The key is the algorithm name
#    (used to select the algorithm in the config). The value is the module
#    defining the expected functions for training and tuning. See the docstring
#    for `get_namespace` for further details.
ALGORITHM_REGISTRATION = {
    'pg': pg_train,
    'ga': ga_train,
    'rand': ga_train,
}


def get_namespace(config_string):
  """Get namespace for the selected algorithm.

  Users who want to add additional algorithm types should modify this function.
  The algorithm's namespace should contain the following functions:
    run_training: Run the main training loop.
    define_tuner_hparam_space: Return the hparam tuning space for the algo.
    write_hparams_to_config: Helper for tuning. Write hparams chosen for tuning
        to the Config object.
  Look at pg_train.py and ga_train.py for function signatures and
  implementations.

  Args:
    config_string: String representation of a Config object. This will get
        parsed into a Config in order to determine what algorithm to use.

  Returns:
    algorithm_namespace: The module corresponding to the algorithm given in the
        config.
    config: The Config object resulting from parsing `config_string`.

  Raises:
    ValueError: If config.agent.algorithm is not one of the registered
        algorithms.
  """
  config = defaults.default_config_with_updates(config_string)
  if config.agent.algorithm not in ALGORITHM_REGISTRATION:
    raise ValueError('Unknown algorithm type "%s"' % (config.agent.algorithm,))
  else:
    return ALGORITHM_REGISTRATION[config.agent.algorithm], config


def main(argv):
  del argv  # Unused.

  logging.set_verbosity(FLAGS.log_level)

  flags.mark_flag_as_required('logdir')
  if FLAGS.num_workers <= 0:
    raise ValueError('num_workers flag must be greater than 0.')
  if FLAGS.task_id < 0:
    raise ValueError('task_id flag must be greater than or equal to 0.')
  if FLAGS.task_id >= FLAGS.num_workers:
    raise ValueError(
        'task_id flag must be strictly less than num_workers flag.')

  ns, _ = get_namespace(FLAGS.config)
  ns.run_training(is_chief=FLAGS.task_id == 0)


if __name__ == '__main__':
  app.run(main)

#This file: code_tasks.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Tasks for RL."""

import abc
import copy
import itertools
import random

from absl import logging
import numpy as np
from six.moves import xrange

from common import bf  # brain coder
from common import reward as r  # brain coder
from single_task import misc  # brain coder
from single_task import test_tasks  # brain coder


MAX_EXECUTION_STEPS = 5000


def make_task(task_name, override_kwargs=None, max_code_length=100,
              require_correct_syntax=False,
              do_code_simplification=False,
              correct_bonus=2.0, code_length_bonus=1.0):
  """Make tasks with setting from paper."""
  logging.info('Making paper-config task.')
  n = 16  # Number of test cases.
  task_mapping = {
      'print-hello': (
          PrintTask, dict(base=27, fixed_string=[8, 5, 12, 12, 15])),
      'print': (PrintIntTask, dict(base=256, fixed_string=[1, 2, 3, 4, 5])),
      'echo': (EchoTask, dict(base=27, min_length=1, max_length=6)),
      'remove-char': (
          RemoveCharTask, dict(base=256, n=n, min_len=1, max_len=6)),
      'reverse': (
          ReverseTask, dict(base=256, n=n, min_len=1, max_len=6)),
      'reverse-tune': (
          ReverseTaskV2, dict(base=256, reward_type='static-bylen')),
      'remove-char-tune': (RemoveCharTaskV2, dict(base=27)),
      'prefix': (CommonPrefixTask, dict(base=27)),
      'find': (FindSubStrTask, dict(base=27)),
      'sort3': (SortFixedTaskV2, dict(base=27, n=150, length=3)),
      'count-char': (CountCharTaskV2, dict(n=n, max_len=6)),
      'bool-logic': (BooleanLogicTask, dict()),
      'add': (AddTask, dict(n=9)),
      'echo-twice': (EchoTwiceTask, dict(n=n)),
      'echo-thrice': (EchoThriceTask, dict(n=n)),
      'copy-reverse': (CopyReverseTask, dict(n=n)),
      'zero-cascade': (EchoZeroCascadeTask, dict(n=n)),
      'cascade': (EchoCascadeTask, dict(n=n)),
      'shift-left': (ShiftLeftTask, dict(n=n)),
      'shift-right': (ShiftRightTask, dict(n=n)),
      'riffle': (RiffleTask, dict(n=n)),
      'unriffle': (UnriffleTask, dict(n=n)),
      'middle-char': (MiddleCharTask, dict(n=n)),
      'remove-last': (RemoveLastTask, dict(n=n)),
      'remove-last-two': (RemoveLastTwoTask, dict(n=n)),
      'echo-alternating': (EchoAlternatingTask, dict(n=n)),
      'echo-half': (EchoHalfTask, dict(n=n)),
      'length': (LengthTask, dict(n=n)),
      'echo-second-seq': (EchoSecondSequenceTask, dict(n=n)),
      'echo-nth-seq': (EchoNthSequenceTask, dict(n=n)),
      'substring': (SubstringTask, dict(n=n)),
      'divide-2': (Divide2Task, dict(n=n)),
      'dedup': (DedupTask, dict(n=n)),
      'remove-target-char': (RemoveTargetCharTask, dict(n=n)),
      'list-index': (ListIndexTask, dict(n=n)),
      'fib': (FibonacciTask, dict()),
      'count-down': (BottlesOfBeerTask, dict()),
      'split': (SplitTask, dict()),
      'trim-left': (TrimLeftTask, dict()),
      'circle-route': (
          JudgeRouteCircleTask, dict(n=100, max_len=32)),
      'multiply': (MultiplyTask, dict(n=100)),
      'divmod': (DivModTask, dict(n=100)),
  }

  if task_name not in task_mapping:
    # Test tasks.
    if task_name == 'test-hill-climb':
      return test_tasks.BasicTaskManager(test_tasks.HillClimbingTask())
    raise ValueError('Unknown task type "%s"' % task_name)
  task_cls, kwargs = task_mapping[task_name]

  if override_kwargs:
    if not isinstance(override_kwargs, dict):
      raise ValueError(
          'override_kwargs must be a dict, got: %s', override_kwargs)
    kwargs.update(override_kwargs)

  task = task_cls(**kwargs)

  reward_fn = r.absolute_distance_reward
  # reward_fn = r.absolute_mod_distance_reward
  # reward_fn = r.absolute_log_distance_reward
  logging.info('Using reward function: %s', reward_fn.__name__)

  # We want reward with and without code simplification to be scaled the same
  # way. Without code simplification, give the maximum code length bonus
  # every time.
  min_code_length = 0.0 if do_code_simplification else max_code_length

  return MultiIOTaskManager(
      task=task, correct_bonus=correct_bonus,
      code_length_bonus=code_length_bonus,
      max_code_length=max_code_length, min_code_length=min_code_length,
      reward_fn=reward_fn, require_correct_syntax=require_correct_syntax)


def concat(lists):
  if not lists:
    return []
  l = lists[0]
  for k in lists[1:]:
    l += k
  return l


def concat_join(lists, sep):
  if not lists:
    return []
  l = lists[0]
  for k in lists[1:]:
    l += [sep] + k
  return l


def clipped_linear(x, x0, y0, slope, y_range):
  min_y, max_y = y_range
  return min(max(slope * (x - x0) + y0, min_y), max_y)


class MultiIOTaskManager(object):
  """Supports tasks which test the code with multiple I/O examples."""

  def __init__(self, task, max_code_length=32, min_code_length=0,
               max_execution_steps=MAX_EXECUTION_STEPS, correct_bonus=1.0,
               code_length_bonus=1.0, failure_reward=-2.0, reward_fn=None,
               require_correct_syntax=False):
    assert isinstance(task, BaseTask)
    self.task = task
    self.max_code_length = max_code_length
    self.min_code_length = min_code_length
    self.max_execution_steps = max_execution_steps
    self.require_correct_syntax = require_correct_syntax
    self.correct_bonus = correct_bonus
    self.code_length_bonus = code_length_bonus
    self.failure_reward = failure_reward
    self.time_penalty = (
        1.0 / (max_code_length - min_code_length)
        if max_code_length > min_code_length else 0.0)
    if reward_fn is None:
      self.reward_fn = r.absolute_distance_reward
    else:
      self.reward_fn = reward_fn
    self.input_type = (
        task.input_type if hasattr(task, 'input_type') else misc.IOType.integer)
    self.output_type = (
        task.output_type if hasattr(task, 'output_type')
        else misc.IOType.integer)
    self._compute_best_reward()

  def _compute_best_reward(self):
    io_seqs = self.task.make_io_set()
    reward = 0.0
    for _, output_seq in io_seqs:
      reward += self.reward_fn(output_seq, output_seq, self.task.base)
      reward += self.correct_bonus
      reward += self.code_length_bonus  # Bonus for shortest code.
    self.best_reward = reward
    self.good_reward = 0.75 * reward
    logging.info('Known best reward: %.4f', self.best_reward)

  def _score_batch(self, code_strings):
    return [self._score_code(code) for code in code_strings]

  def _score_code(self, code):
    """Run test cases on code and compute reward.

    Args:
      code: A single BF code string.

    Returns:
      misc.RewardInfo namedtuple instance containing reward and code execution
          information, including inputs, expected outputs, code outputs, input
          and output types, and reason for the reward obtained.
    """
    # Get list of 2-tuples, each containing an input sequence and an output
    # sequence.
    io_seqs = self.task.make_io_set()
    terminal_reward = 0.0
    results = []
    reason = 'correct'
    for input_seq, output_seq in io_seqs:
      eval_result = bf.evaluate(
          code, input_buffer=input_seq, timeout=0.1,
          max_steps=self.max_execution_steps,
          base=self.task.base,
          require_correct_syntax=self.require_correct_syntax)
      result, success = eval_result.output, eval_result.success
      if not success:
        # Code execution timed out.
        terminal_reward = self.failure_reward
        results = []
        reason = eval_result.failure_reason
        break
      else:
        terminal_reward += self.reward_fn(result, output_seq, self.task.base)
        if result == output_seq:
          terminal_reward += self.correct_bonus  # Bonus for correct answer.

          # Only add additional reward for shorter code. Subtracting reward
          # interferes with the main objective. Only optimize for length once
          # any solution is found.
          if self.min_code_length == self.max_code_length:
            terminal_reward += self.code_length_bonus
          else:
            terminal_reward += self.code_length_bonus * clipped_linear(
                x=len(code), x0=self.min_code_length, y0=1.0,
                slope=-self.time_penalty, y_range=(0.0, 1.0))

          # reason remains 'correct' if it is already
        elif reason == 'correct':
          reason = 'wrong'
      results.append(result)

    # Return list of rewards, one for each char in the code. All are 0 except
    # for the terminal reward.
    terminal_reward /= self.best_reward
    return misc.RewardInfo(
        episode_rewards=[0.0] * (len(code) - 1) + [terminal_reward],
        input_case=misc.IOTuple(i for i, o in io_seqs),
        correct_output=misc.IOTuple(o for i, o in io_seqs),
        code_output=misc.IOTuple(results),
        input_type=self.input_type,
        output_type=self.output_type,
        reason=reason)

  def rl_batch(self, batch_size):
    """Produces list of reward functions. One for each program in the batch."""
    return [self._score_code] * batch_size


def conditional_overwrite(current_value, new_value, allowed_overwrite_values):
  if current_value in allowed_overwrite_values:
    return new_value
  return current_value


class BaseTask(object):
  """A coding task.

  All coding tasks should inherit this class.
  """
  __metaclass__ = abc.ABCMeta

  def __init__(self, base=256):
    self.base = base  # All tasks must set the integer base that the expect.

  @abc.abstractmethod
  def make_io_set(self):
    """Generate a set of test cases for the task.

    Returns:
      List of tuples, where each tuple is (input_case, output_case).
      input_case and output_case are lists of integers.
    """
    pass


# ==============================================================================
# ICLR tasks.
# ==============================================================================


class PrintTask(BaseTask):
  """Print string coding task.

  Code needs to output a fixed string (given as a hyperparameter to the
  task constructor). Program input is ignored.
  """

  def __init__(self, base, fixed_string=None):
    super(type(self), self).__init__()
    self.base = base  # base includes EOS
    self.eos = 0
    if fixed_string:
      self.fixed_string = fixed_string
    else:
      self.fixed_string = [1, 2, 3, 0]  # ABC<EOS>
    self.min_length = self.max_length = len(self.fixed_string)

  def make_io_set(self):
    return [(list(), list(self.fixed_string))]


class RemoveCharTaskV2(BaseTask):
  """Remove character coding task (version 2).

  Code needs to pipe input to output, but with all the 'A' (value 1) chars
  removed. 'A' appears exactly once in each input.

  Test cases are hard-coded.
  """

  def __init__(self, base):
    super(type(self), self).__init__()
    self.base = base
    self.eos = 0
    self.remove_char = 1
    assert base >= 27

  def make_io_set(self):
    rm = self.remove_char
    return [
        ([rm, 0], [0]),
        ([20, rm, 0], [20, 0]),
        ([rm, 13, 0], [13, 0]),
        ([6, rm, 17, 0], [6, 17, 0]),
        ([rm, 11, 24, 0], [11, 24, 0]),
        ([2, 16, 21, rm, 0], [2, 16, 21, 0]),
        ([18, rm, 12, 26, 7, 0], [18, 12, 26, 7, 0]),
        ([9, 10, 22, rm, 4, 0], [9, 10, 22, 4, 0])]


class RemoveCharTask(BaseTask):
  """Remove character coding task.

  Code needs to pipe input to output, but with all the 'A' (value 1) chars
  removed. 'A' appears at least once in each input.

  Test cases are dynamically generated, allowing for the number of test cases
  to be a hyperparameter.
  """

  def __init__(self, base, n, min_len, max_len):
    super(type(self), self).__init__()
    self.base = base
    self.eos = 0
    self.remove_char = 1
    assert base >= 27
    self._io_pairs = self._make_io_examples(n, min_len, max_len)

  def _make_io_examples(self, n, min_len, max_len):
    """Generate test cases for the task."""
    rand = random.Random(6849275409234)  # Test cases are fixed, but varied.
    io_examples = []
    for _ in xrange(n):
      length = rand.randrange(min_len, max_len + 1)
      rm_char_pos = rand.randrange(0, length)
      input_seq = [rand.randrange(1, self.base) for _ in xrange(length)]
      input_seq[rm_char_pos] = self.remove_char
      output_seq = list(input_seq)
      del output_seq[rm_char_pos]
      output_seq.append(0)
      io_examples.append((input_seq, output_seq))
    return io_examples

  def make_io_set(self):
    return copy.deepcopy(self._io_pairs)


class ReverseTaskV2(BaseTask):
  """Reverse string coding task (version 2).

  Code needs to pipe input to output, but in reverse order.

  Stochastic test case = new test case randomly generated for every run of
  `make_io_set`, i.e. different test cases every time code is scored.

  Task supports different types of test cases:
    rand-one: Code is scored on one stochastic test case.
    rand-many: Code is scored on 5 stochastic test cases.
    static-bylen: Code is scored on 5 static test cases. There is one test
        case for string lengths 1 through 5.
    rand-bylen: Code is scored on 5 stochastic test cases, where there is one
        test case for string lengths 1 through 5.
  """

  def __init__(self, base, reward_type):
    super(type(self), self).__init__()
    self.base = base  # base includes EOS
    assert base >= 27
    self.eos = 0
    self.io_pair_fn = {
        # One random example at a time.
        'rand-one': lambda: self._io_rand(1),
        # K randomy examples at a time (any lengths).
        'rand-many': lambda: self._io_rand(5),
        # Static examples, one for each length.
        'static-bylen': self._io_static_by_len,
        # Random examples, one for each length.
        'rand-bylen': self._io_rand_by_len}[reward_type]

  def _make_io_examples(self, sequences):
    outputs = [list(i) for i in sequences]
    for o in outputs:
      o.reverse()
      o.append(0)
    inputs = [i + [0] for i in sequences]
    return zip(inputs, outputs)

  def _io_rand(self, k):
    inputs = [(np.random.choice(26, random.randrange(1, 6)) + 1).tolist()
              for _ in xrange(k)]
    return self._make_io_examples(inputs)

  def _io_rand_by_len(self, k=5):
    inputs = [(np.random.choice(26, length) + 1).tolist()
              for length in xrange(1, k + 1)]
    return self._make_io_examples(inputs)

  def _io_static_by_len(self):
    return [
        ([7, 0], [7, 0]),
        ([6, 2, 0], [2, 6, 0]),
        ([5, 1, 10, 0], [10, 1, 5, 0]),
        ([8, 6, 5, 15, 0], [15, 5, 6, 8, 0]),
        ([10, 12, 5, 2, 7, 0], [7, 2, 5, 12, 10, 0])]

  def make_io_set(self):
    return self.io_pair_fn()


class ReverseTask(BaseTask):
  """Reverse string coding task.

  Code needs to pipe input to output, but in reverse order.

  Test cases are dynamically generated, allowing for the number of test cases
  to be a hyperparameter.
  """

  def __init__(self, base, n, min_len, max_len):
    super(type(self), self).__init__()
    self.base = base  # base includes EOS
    assert base >= 27
    self.eos = 0
    self._io_pairs = self._make_io_examples(n, min_len, max_len)

  def _make_io_examples(self, n, min_len, max_len):
    """Generate test cases for the task."""
    rand = random.Random(6849275409234)  # Test cases are fixed, but varied.
    io_examples = []
    for _ in xrange(n):
      length = rand.randrange(min_len, max_len + 1)
      input_seq = [rand.randrange(1, self.base) for _ in xrange(length)]
      output_seq = list(input_seq)
      output_seq.reverse()
      output_seq.append(0)
      io_examples.append((input_seq, output_seq))
    return io_examples

  def make_io_set(self):
    return copy.deepcopy(self._io_pairs)


class CommonPrefixTask(BaseTask):
  """Common prefix coding task.

  Code needs to output the common prefix between two input lists. Input lists
  are variable length, where each list ends with a 0. A common prefix is a
  sequence which both lists start with.
  """

  def __init__(self, base):
    super(type(self), self).__init__()
    assert base >= 27
    self.base = base
    self.eos = 0

  def make_io_set(self):
    return [
        ([12, 24, 18, 0, 12, 5, 0], [12, 0]),
        ([1, 2, 3, 0, 1, 2, 17, 14, 0], [1, 2, 0]),
        ([15, 2, 1, 9, 2, 0, 15, 2, 1, 25, 8, 14, 0], [15, 2, 1, 0]),
        ([14, 9, 7, 8, 6, 16, 0, 14, 9, 7, 8, 8, 6, 8, 26, 0],
         [14, 9, 7, 8, 0]),
        ([12, 4, 16, 22, 1, 17, 0, 12, 4, 16, 22, 1, 8, 10, 0],
         [12, 4, 16, 22, 1, 0])]


class CountCharTask(BaseTask):

  def __init__(self):
    super(type(self), self).__init__()
    self.base = 27
    self.eos = 0
    self.char = 1
    self.input_type = misc.IOType.string
    self.output_type = misc.IOType.integer

  def make_io_set(self):
    return [
        ([10, 0], [0]),
        ([1, 0], [1]),
        ([1, 1, 0], [2]),
        ([11, 1, 0], [1]),
        ([1, 24, 0], [1]),
        ([13, 6, 0], [0]),
        ([9, 2, 7, 0], [0]),
        ([1, 24, 11, 0], [1]),
        ([19, 1, 1, 0], [2]),
        ([1, 6, 1, 0], [2]),
        ([22, 16, 17, 9, 0], [0]),
        ([1, 1, 1, 19, 0], [3]),
        ([1, 1, 1, 1, 0], [4]),
        ([9, 4, 19, 11, 5, 0], [0]),
        ([24, 11, 26, 1, 15, 0], [1]),
        ([1, 1, 20, 1, 1, 0], [4]),
        ([1, 1, 1, 1, 1, 0], [5])]


class CountCharTaskV2(BaseTask):
  """Count char coding task (version 2).

  Code must output the number of occurances of character 'A' (value 1) in an
  input string.

  Test cases are dynamically generated, allowing for the number of test cases
  to be a hyperparameter.
  """

  def __init__(self, n, max_len):
    super(type(self), self).__init__()
    self.base = 27
    self.eos = 0
    self.char = 1
    self.other_chars = [c for c in xrange(self.base)
                        if c not in (self.eos, self.char)]
    self.input_type = misc.IOType.string
    self.output_type = misc.IOType.integer
    self._io_pairs = self._make_io_examples(n, max_len)

  def _make_io_examples(self, n, max_len):
    """Generate test cases for the task."""
    rand = random.Random(6849275409234)  # Test cases are fixed, but varied.
    io_examples = []
    io_examples.append(([10, 0], [0]))
    io_examples.append(([1, 0], [1]))
    io_examples.append(([1, 1, 0], [2]))
    io_examples.append(([9, 4, 19, 11, 5, 0], [0]))
    io_examples.append(([24, 11, 26, 1, 15, 0], [1]))
    for _ in xrange(n - 5):
      length = rand.randrange(2, max_len + 1)
      num_chars = rand.randrange(0, max_len + 1)
      input_seq = [self.char] * num_chars + [0] * (length - num_chars)
      rand.shuffle(input_seq)
      for i in xrange(len(input_seq)):
        if not input_seq[i]:
          input_seq[i] = self.other_chars[rand.randrange(len(self.other_chars))]
      output_seq = [num_chars]
      io_examples.append((input_seq, output_seq))
    return io_examples

  def make_io_set(self):
    return copy.deepcopy(self._io_pairs)


class AddTask(BaseTask):
  """Addition coding task.

  Code needs to read in two integers and output their sum mod the BF base,
  followed by a terminating 0.
  """

  def __init__(self, n=16):
    super(type(self), self).__init__()
    self.base = 256
    self.input_type = misc.IOType.integer
    self.output_type = misc.IOType.integer
    self._io_pairs = self._make_io_examples(n)

  def _make_io_examples(self, n):
    """Generate test cases for the task."""
    rand = random.Random(6849275409234)  # Test cases are fixed, but varied.
    io_examples = [
        ([4, 0], [4, 0]),
        ([0, 5], [5, 0]),
        ([1, 2], [3, 0]),
        ([67, 21], [88, 0]),
        ([55, 56], [111, 0]),
        ([128, 33], [161, 0]),
        ([221, 251], [216, 0]),
        ([130, 127], [1, 0]),
        ([255, 1], [0, 0])]
    extra_examples = max(n - len(io_examples), 0)
    for _ in xrange(extra_examples):
      a = rand.randrange(256)
      b = rand.randrange(256)
      input_seq = [a, b]
      output_seq = [(a + b) % 256, 0]
      io_examples.append((input_seq, output_seq))
    return io_examples

  def make_io_set(self):
    return copy.deepcopy(self._io_pairs)


class BooleanLogicTask(BaseTask):
  """Boolean logic (truth table) coding task.

  Code needs to memorize a boolean truth table. Specifically, it must encode a
  mapping from triple of bools to a single bool.
  """

  def __init__(self):
    super(type(self), self).__init__()
    self.base = 2
    self.input_type = misc.IOType.boolean
    self.output_type = misc.IOType.boolean
    # X(~Z) + (~Y)(~Z) + (~X)YZ
    self._truth_fn = (
        lambda x, y, z:  # pylint: disable=g-long-lambda
        (x and not z) or (not y and not z) or (not x and y and z))
    self._test_cases = [
        ([x, y, z], [int(self._truth_fn(x, y, z))])
        for x, y, z in itertools.product(range(2), range(2), range(2))]

  def make_io_set(self):
    return copy.deepcopy(self._test_cases)


# ------------------------------------------------------------------------------
# The following tasks are generated from known BF solutions. This guarantees
# that each task can be solved within the maximum code length, and maximum
# execution steps.
# ------------------------------------------------------------------------------


def default_input_fn_factory(min_length=1, max_length=6, base=256):
  def _input_gen(rand):
    l = rand.randrange(min_length, max_length + 1)
    return [rand.randrange(base) for _ in xrange(l)]
  return _input_gen


class KnownCodeBaseTask(BaseTask):
  """These tasks generate their test cases from a known BF solution.

  This ensures that each task has a solution which is under the max character
  length, and that it solves the test cases under the max number of execution
  steps.
  """

  def __init__(self, code_solution, make_input_fn, n=100, base=256,
               max_steps=5000, seed=6849275409234):
    super(KnownCodeBaseTask, self).__init__()
    # Make sure known solution is less than the code length used in experiments.
    assert len(code_solution) < 100
    self.code_solution = code_solution
    self.make_input_fn = make_input_fn
    self.n = n
    self.base = base
    self.max_steps = max_steps
    self.seed = seed
    self._test_cases = list(self._test_case_generator(code_solution))

  def _test_case_generator(self, code_solution):
    rand = random.Random(self.seed)
    for _ in xrange(self.n):
      input_case = self.make_input_fn(rand)
      result = bf.evaluate(
          code_solution, input_buffer=input_case, max_steps=self.max_steps,
          base=self.base, require_correct_syntax=False)
      if not result.success:
        raise RuntimeError(
            'Program must succeed. Failed on input: %s' % input_case)
      yield input_case, result.output

  def make_io_set(self):
    return copy.deepcopy(self._test_cases)


class EchoTwiceTask(KnownCodeBaseTask):
  """Echo twice."""

  def __init__(self, **kwargs):
    super(type(self), self).__init__(
        '>,.[>,.]<[<]>[.>].',
        default_input_fn_factory(),
        **kwargs)


class EchoThriceTask(KnownCodeBaseTask):
  """Echo three times."""

  def __init__(self, **kwargs):
    super(type(self), self).__init__(
        '>,.[>,.]<[<]>[.>].<[<]>[.>].',
        default_input_fn_factory(),
        **kwargs)


class CopyReverseTask(KnownCodeBaseTask):
  """Echo forwards, backwards, and then forwards again."""

  def __init__(self, **kwargs):
    super(type(self), self).__init__(
        '>,.[>,.]<[.<].>[.>].',
        default_input_fn_factory(),
        **kwargs)


class EchoZeroCascadeTask(KnownCodeBaseTask):
  """Print k-th char with k zeros inbetween (1-indexed)."""

  def __init__(self, **kwargs):
    super(type(self), self).__init__(
        ',[.>[->+>.<<]>+[-<+>]<<,]',
        default_input_fn_factory(),
        **kwargs)


class EchoCascadeTask(KnownCodeBaseTask):
  """Print k-th char k times (1-indexed)."""

  def __init__(self, **kwargs):
    super(type(self), self).__init__(
        ',>>+<<[>>[-<+>]<[->+<<.>]>+<<,].',
        default_input_fn_factory(base=20),
        **kwargs)


class ShiftLeftTask(KnownCodeBaseTask):
  """Circulate shift input left."""

  def __init__(self, **kwargs):
    super(type(self), self).__init__(
        ',>,[.,]<.,.',
        default_input_fn_factory(),
        **kwargs)


class ShiftRightTask(KnownCodeBaseTask):
  """Circular shift input right."""

  def __init__(self, **kwargs):
    super(type(self), self).__init__(
        '>,[>,]<.[-]<[<]>[.>].',
        default_input_fn_factory(),
        **kwargs)


class RiffleTask(KnownCodeBaseTask):
  """Shuffle like a deck of cards.

  For input of length N, output values in the following index order:
  N-1, 0, N-2, 1, N-3, 2, ...
  """

  def __init__(self, **kwargs):
    super(type(self), self).__init__(
        '>,[>,]<[.[-]<[<]>.[-]>[>]<]',
        default_input_fn_factory(base=20, max_length=8),
        **kwargs)


class UnriffleTask(KnownCodeBaseTask):
  """Inverse of riffle."""

  def __init__(self, **kwargs):
    super(type(self), self).__init__(
        '>,[>,[.[-]],]<[.<].',
        default_input_fn_factory(base=20, max_length=8),
        **kwargs)


class MiddleCharTask(KnownCodeBaseTask):
  """Print middle char if length is odd, or 0 if even."""

  def __init__(self, **kwargs):
    super(type(self), self).__init__(
        '>,[>,]<<[[>]<[,<[<]>,>[>]][>]<<]>.',
        default_input_fn_factory(max_length=10),
        **kwargs)


class RemoveLastTask(KnownCodeBaseTask):
  """Remove last character."""

  def __init__(self, **kwargs):
    super(type(self), self).__init__(
        ',>,[[<.[-]>[-<+>]],].',
        default_input_fn_factory(base=20),
        **kwargs)


class RemoveLastTwoTask(KnownCodeBaseTask):
  """Remove last two characters."""

  def __init__(self, **kwargs):
    super(type(self), self).__init__(
        ',>,>,[[<<.[-]>[-<+>]>[-<+>]],].',
        default_input_fn_factory(base=10),
        **kwargs)


class EchoAlternatingTask(KnownCodeBaseTask):
  # Print even numbered chars first (0-indexed), then odd numbered chars

  def __init__(self, **kwargs):
    super(type(self), self).__init__(
        '>,[.,>,]<<[<]>[.>].',
        default_input_fn_factory(base=20, max_length=8),
        **kwargs)


class EchoHalfTask(KnownCodeBaseTask):
  """Echo only first half of the input (round down when odd lengthed)."""

  def __init__(self, **kwargs):
    super(type(self), self).__init__(
        '>>+>,[[<]>+[>],]<[<]>-[-[-<<+>]<[>]>]<<[->+<]>[[>]>.,<+[<]>-].',
        default_input_fn_factory(base=20, max_length=9),
        **kwargs)


class LengthTask(KnownCodeBaseTask):
  """Print length of the input sequence."""

  def __init__(self, **kwargs):
    super(type(self), self).__init__(
        '>+>,[[<]>+[>],]<[<]>-.',
        default_input_fn_factory(max_length=14),
        **kwargs)


class EchoSecondSequenceTask(KnownCodeBaseTask):
  """Echo second sequence. Sequences are separated by 0."""

  def __init__(self, **kwargs):
    def echo_second_gen(rand):
      l = rand.randrange(1, 6)
      x = [rand.randrange(256) for _ in xrange(l)]
      l = rand.randrange(1, 6)
      y = [rand.randrange(256) for _ in xrange(l)]
      return x + [0] + y + [0]
    super(type(self), self).__init__(
        ',[,],[.,].',
        echo_second_gen,
        **kwargs)


class EchoNthSequenceTask(KnownCodeBaseTask):
  """Echo n-th sequence (1-indexed). Sequences are separated by 0."""

  def __init__(self, **kwargs):
    def echo_nth_gen(rand):
      k = rand.randrange(1, 7)
      n = rand.randrange(1, k + 1)
      x = []
      for _ in xrange(k):
        l = rand.randrange(0, 4)
        x += [rand.randrange(256) for _ in xrange(l)] + [0]
      return [n] + x
    super(type(self), self).__init__(
        ',-[->,[,]<],[.,].',
        echo_nth_gen,
        **kwargs)


class SubstringTask(KnownCodeBaseTask):
  """Echo substring.

  First two inputs are i and l, where i is the starting index (0-indexed)
  and l is the length of the substring.
  """

  def __init__(self, **kwargs):
    def substring_gen(rand):
      l = rand.randrange(2, 16)
      i, j = sorted([rand.randrange(l), rand.randrange(l)])
      n = j - i
      x = [rand.randrange(256) for _ in xrange(l)] + [0]
      return [i, n] + x
    super(type(self), self).__init__(
        '>,<,>[->,<]>,<<[->>.,<<]',
        substring_gen,
        **kwargs)


class Divide2Task(KnownCodeBaseTask):
  """Divide by 2 (integer floor division)."""

  def __init__(self, **kwargs):
    def int_input_gen(rand):
      return [rand.randrange(256)]
    super(type(self), self).__init__(
        ',[-[->>+<]>[<]<]>>.',
        int_input_gen,
        **kwargs)


class DedupTask(KnownCodeBaseTask):
  """Deduplicate adjacent duplicate chars."""

  def __init__(self, **kwargs):
    def dedup_input_gen(rand):
      np_random = np.random.RandomState(rand.randrange(2147483647))
      num_unique = rand.randrange(1, 5)
      unique = np_random.choice(6, num_unique, replace=False) + 1
      return [v for v in unique for _ in xrange(rand.randrange(1, 5))] + [0]
    super(type(self), self).__init__(
        '>>,.[[-<+<+>>],[-<->]<[[-<->]<.>]<[->>+<<]>>]',
        dedup_input_gen,
        **kwargs)


# ==============================================================================
# Extra tasks.
# ==============================================================================


class PrintIntTask(BaseTask):
  """Print integer coding task.

  Code needs to output a fixed single value (given as a hyperparameter to the
  task constructor). Program input is ignored.
  """

  def __init__(self, base, fixed_string):
    super(type(self), self).__init__()
    self.base = base
    self.eos = 0
    self.fixed_string = fixed_string
    self.input_type = misc.IOType.integer
    self.output_type = misc.IOType.integer

  def make_io_set(self):
    return [(list(), list(self.fixed_string))]


class EchoTask(BaseTask):
  """Echo string coding task.

  Code needs to pipe input to putput (without any modifications).
  """

  def __init__(self, base, min_length=1, max_length=5):
    super(type(self), self).__init__()
    self.base = base  # base includes EOS
    self.eos = 0
    self.min_length = min_length
    self.max_length = max_length
    self._io_pairs = self._make_io_examples(25)

  def _make_io_examples(self, n):
    # Test cases are fixed, but varied.
    np_random = np.random.RandomState(1234567890)
    io_pairs = []
    for _ in xrange(n):
      length = np_random.randint(self.min_length, self.max_length + 1)
      input_seq = np_random.randint(1, self.base, length).tolist() + [self.eos]
      output_seq = list(input_seq)
      io_pairs.append((input_seq, output_seq))
    return io_pairs

  def make_io_set(self):
    return copy.deepcopy(self._io_pairs)


class JudgeRouteCircleTask(BaseTask):
  """Judge route circle coding task.

  Code needs to determine if the given route makes a closed loop.
  Encoding: U = 1, R = 2, D = 3, L = 4.

  Based on
  https://leetcode.com/problems/judge-route-circle/description/
  """
  base = 256
  input_type = misc.IOType.integer
  output_type = misc.IOType.integer

  def __init__(self, n, max_len=12):
    super(type(self), self).__init__()
    self.eos = 0
    self._io_pairs = self._make_io_examples(n, max_len)
    self.input_type = misc.IOType.integer
    self.output_type = misc.IOType.integer

  def _solve(self, input_seq):
    assert input_seq[-1] == 0
    pos = [0, 0]  # (x, y)
    for move in input_seq[:-1]:
      assert 0 < move <= 4
      if move & 1 == 0:  # Left or Right.
        pos[0] += 3 - move  # Add or subtract 1.
      else:
        pos[1] += 2 - move  # Add or subtract 1.
    return [int(not pos[0] and not pos[1])]

  def _make_io_examples(self, n, max_len):
    """Generate test cases for the task."""
    rand = random.Random(6849275409234)  # Test cases are fixed, but varied.
    io_examples = []
    io_examples.append(([0], [1]))
    io_examples.append(([4, 2, 0], [1]))
    io_examples.append(([2, 4, 0], [1]))
    io_examples.append(([3, 1, 0], [1]))
    io_examples.append(([1, 3, 0], [1]))
    io_examples.append(([1, 0], [0]))
    io_examples.append(([2, 0], [0]))
    io_examples.append(([3, 0], [0]))
    io_examples.append(([4, 0], [0]))
    for _ in xrange(n):
      is_true = rand.randrange(2)
      length = rand.randrange(1, max_len + 1)
      if is_true:
        # Make a true case.
        length = (length >> 1) << 1  # Make even.
        partition = (rand.randrange(length + 1) >> 1) << 1
        a = partition >> 1
        b = (length - partition) >> 1
        counts = {1: a, 2: b, 3: a, 4: b}
      else:
        # Make a false case.
        partitions = (
            [0]
            + sorted([rand.randrange(length + 1) for _ in range(3)])
            + [length])
        counts = {n: partitions[n] - partitions[n - 1] for n in range(1, 5)}
        if counts[1] == counts[3] and counts[2] == counts[4]:
          # By chance we sampled a true case. Make it false by exchanging
          # one count between even and odd pairs.
          base = 1 + 2 * rand.randrange(2)
          a, b = (base, base + 1) if rand.randrange(2) else (base + 1, base)
          if counts[a] == length or counts[b] == 0:
            # If counts are at their extreme values, then swap who gets
            # incremented and decremented.
            a, b = b, a
          counts[a] += 1
          counts[b] -= 1
          assert counts[a] <= length and counts[b] >= 0
      assert sum(counts.values()) == length
      input_seq = [n for n in xrange(1, 5) for _ in xrange(counts[n])]
      rand.shuffle(input_seq)
      input_seq += [0]
      output_seq = self._solve(input_seq)
      assert output_seq[0] == is_true
      io_examples.append((input_seq, output_seq))
    return io_examples

  def make_io_set(self):
    return copy.deepcopy(self._io_pairs)


class MultiplyTask(BaseTask):
  """Multiply coding task.

  Code needs to multiple two ints.

  Solution:
  http://robl.co/brief-look-at-brainfuck/
  ,>,><<[->[->+>+<<]>>[-<<+>>]<<<]>>.
  """
  base = 512
  input_type = misc.IOType.integer
  output_type = misc.IOType.integer

  def __init__(self, n):
    super(type(self), self).__init__()
    self.eos = 0
    self._io_pairs = self._make_io_examples(n)
    self.input_type = misc.IOType.integer
    self.output_type = misc.IOType.integer

  def _factors(self, n):
    return set(i for i in range(1, int(n**0.5) + 1) if n % i == 0)

  def _make_io_examples(self, n):
    """Generate test cases for the task."""
    rand = random.Random(6849275409234)  # Test cases are fixed, but varied.
    io_examples = []
    for _ in xrange(n):
      n = rand.randrange(self.base)
      if n == 0:
        a, b = 0, rand.randrange(self.base)
      else:
        f = list(self._factors(n))
        a = f[rand.randrange(len(f))]
        b = n // a
      if rand.randrange(2):
        a, b = b, a
      io_examples.append(([a, b], [n]))
    return io_examples

  def make_io_set(self):
    return copy.deepcopy(self._io_pairs)


class DivModTask(BaseTask):
  """Divmod coding task.

  Code needs to take the quotient and remainder of two ints.

  Solution:
  http://robl.co/brief-look-at-brainfuck/
  ,>,><<[>[->+>+<<]>[-<<-[>]>>>[<[-<->]<[>]>>[[-]>>+<]>-<]<<]>>>+<<[-<<+>>]<<<]>
  >>>>[-<<<<<+>>>>>]<<<<<.>.>
  """
  base = 512
  input_type = misc.IOType.integer
  output_type = misc.IOType.integer

  def __init__(self, n):
    super(type(self), self).__init__()
    self.eos = 0
    self._io_pairs = self._make_io_examples(n)
    self.input_type = misc.IOType.integer
    self.output_type = misc.IOType.integer

  def _make_io_examples(self, n):
    rand = random.Random(6849275409234)  # Test cases are fixed, but varied.
    io_examples = []
    for _ in xrange(n):
      n = rand.randrange(0, self.base)
      k = rand.randrange(1, self.base)  # Divisor cannot be 0.
      io_examples.append(([n, k], list(divmod(n, k))))
    return io_examples

  def make_io_set(self):
    return copy.deepcopy(self._io_pairs)


class FibonacciTask(BaseTask):

  def __init__(self):
    super(type(self), self).__init__()
    self.base = 256
    self.input_type = misc.IOType.integer
    self.output_type = misc.IOType.integer

  def make_io_set(self):
    return [
        ([0], [0, 1]),
        ([1], [1, 1]),
        ([2], [1, 2]),
        ([3], [2, 3]),
        ([4], [3, 5]),
        ([5], [5, 8]),
        ([6], [8, 13]),
        ([7], [13, 21]),
        ([8], [21, 34]),
        ([9], [34, 55]),
        ([10], [55, 89]),
        ([11], [89, 144]),
        ([12], [144, 233]),
        ([13], [233, 121])]


class FindSubStrTask(BaseTask):
  """Find sub-string coding task.

  Code needs to output a bool: True if the input string contains a hard-coded
  substring, 'AB' (values [1, 2]).
  """

  def __init__(self, base):
    super(type(self), self).__init__()
    assert base >= 27
    self.base = base
    self.eos = 0
    self.find_str = [1, 2]
    self.input_type = misc.IOType.string
    self.output_type = misc.IOType.boolean

  def make_io_set(self):
    return [
        ([1, 1, 23, 0], [0]),
        ([21, 3, 2, 0], [0]),
        ([2, 1, 19, 0], [0]),
        ([2, 24, 15, 3, 0], [0]),
        ([24, 6, 10, 16, 4, 0], [0]),
        ([1, 2, 12, 0], [1]),
        ([7, 1, 2, 0], [1]),
        ([1, 2, 11, 3, 0], [1]),
        ([1, 1, 2, 18, 0], [1]),
        ([7, 25, 1, 2, 0], [1]),
        ([3, 1, 2, 11, 8, 0], [1]),
        ([15, 16, 20, 1, 2, 0], [1])]


class SortFixedTask(BaseTask):
  """Sort list coding task.

  Code needs to output a sorted input list. The task consists of lists of the
  same length L, where L is provided to this task's constructor as a
  hyperparameter.
  """

  def __init__(self, base, length=3):
    super(type(self), self).__init__()
    assert base >= 27
    self.base = base
    self.eos = 0
    self.length = length
    assert length == 3  # More lengths will be supported.

  def make_io_set(self):
    if self.length == 3:
      return [
          ([1, 20, 6], [1, 6, 20]),
          ([13, 6, 7], [6, 7, 13]),
          ([24, 2, 23], [2, 23, 24]),
          ([16, 12, 3], [3, 12, 16]),
          ([11, 24, 4], [4, 11, 24]),
          ([10, 1, 19], [1, 10, 19])]


class SortFixedTaskV2(BaseTask):
  """Sort list coding task (version 2).

  Code needs to output a sorted input list. The task consists of lists of the
  same length L, where L is provided to this task's constructor as a
  hyperparameter.

  Test cases are dynamically generated, allowing for the number of test cases
  to be a hyperparameter.
  """

  def __init__(self, base, n, length=3):
    super(type(self), self).__init__()
    assert base >= 27
    self.base = base
    self.eos = 0
    self._io_pairs = self._make_io_examples(n, length)
    self.input_type = misc.IOType.integer
    self.output_type = misc.IOType.integer

  def _make_io_examples(self, n, length):
    rand = random.Random(6849275409234)  # Test cases are fixed, but varied.
    io_examples = []
    for _ in xrange(n):
      input_seq = [rand.randrange(1, self.base) for _ in xrange(length)]
      output_seq = sorted(input_seq)
      io_examples.append((input_seq, output_seq))
    return io_examples

  def make_io_set(self):
    return copy.deepcopy(self._io_pairs)


class RemoveTargetCharTask(KnownCodeBaseTask):
  """Remove target character from string, where first input is the target.

  Target can appear multiple times.
  """

  def __init__(self, **kwargs):
    def randrange_hole(rand, a, hole, b):
      x = rand.randrange(a, b - 1)
      if x >= hole:
        return x + 1
      return x
    def remove_target_char_gen(rand):
      char = rand.randrange(1, 6)
      l = rand.randrange(1, 8)
      input_seq = [randrange_hole(rand, 1, char, 256) for _ in xrange(l)]
      idx = range(l)
      rand.shuffle(idx)
      num_targets = rand.randrange(0, l)
      for pos in idx[:num_targets]:
        input_seq[pos] = char
      return [char] + input_seq + [0]
    super(type(self), self).__init__(
        ',>>>,[<<<[->+>+<<]>>[->->+<<]>[>[-<+>]<.[-]]>[-]<<<[-<+>]>>,].',
        remove_target_char_gen,
        **kwargs)


class ListIndexTask(KnownCodeBaseTask):
  """Echo i-th value in the given list."""

  def __init__(self, **kwargs):
    def array_index_gen(rand):
      l = rand.randrange(1, 16)
      i = rand.randrange(l)
      return [i] + [rand.randrange(256) for _ in xrange(l)] + [0]
    super(type(self), self).__init__(
        ',[->,<]>,.',
        array_index_gen,
        **kwargs)


# ==============================================================================
# Tasks based on primaryobjects paper.
# ==============================================================================


def string2tokens(string):
  return [ord(c) for c in string]


def stringlist2tokens(strings):
  return [string2tokens(string) for string in strings]


def string2tokens_b27(string):
  return [ord(c.lower()) - ord('a') + 1 for c in string]


def stringlist2tokens_b27(strings):
  return [string2tokens_b27(string) for string in strings]


class BottlesOfBeerTask(BaseTask):
  """Bottles of beer coding task.

  This is a counting task. Code needs to read in an int N and then output
  every int from N to 0, each separated by a 0.
  """
  base = 256
  input_type = misc.IOType.integer
  output_type = misc.IOType.integer

  def make_io_set(self):
    return [
        ([1], [1, 0]),
        ([2], [2, 0, 1, 0]),
        ([3], [3, 0, 2, 0, 1, 0]),
        ([4], [4, 0, 3, 0, 2, 0, 1, 0]),
        ([5], [5, 0, 4, 0, 3, 0, 2, 0, 1, 0]),
        ([6], [6, 0, 5, 0, 4, 0, 3, 0, 2, 0, 1, 0])]


class SplitTask(BaseTask):
  """Split coding task.

  Code needs to pipe input strings to output, but insert a 0 after every 3
  characters. This is in essence splitting the string into intervals of length
  3.
  """
  base = 28
  input_type = misc.IOType.string
  output_type = misc.IOType.integer

  def _splicer(self, lst, insert, interval=3):
    for i, item in enumerate(lst):
      yield item
      if (i + 1) % interval == 0 and i < len(lst) - 1:
        yield insert

  def __init__(self):
    super(type(self), self).__init__()
    inputs = stringlist2tokens_b27(
        ['hello', 'orange', 'spaghetti', 'wins', 'one'])
    targets = [list(self._splicer(i, 27)) for i in inputs]
    self._test_cases = list(zip(inputs, targets))

  def make_io_set(self):
    return copy.deepcopy(self._test_cases)


class TrimLeftTask(BaseTask):
  """Trim left coding task.

  Code needs to pipe input strings to output, but remove everything before the
  first quotation char (").
  """
  base = 256
  input_type = misc.IOType.integer
  output_type = misc.IOType.integer

  def __init__(self):
    super(type(self), self).__init__()
    inputs = stringlist2tokens(
        ['a "inside" over', 'xy "test" rights', 'ca6 "foresting" service',
         'abc"def"yz.', 'A"B"'])
    targets = stringlist2tokens(
        ['"inside" over', '"test" rights', '"foresting" service', '"def"yz.',
         '"B"'])
    self._test_cases = list(zip(inputs, targets))

  def make_io_set(self):
    return copy.deepcopy(self._test_cases)

#This file: run_eval_tasks.py
#!/usr/bin/env python
from __future__ import print_function

r"""This script can launch any eval experiments from the paper.

This is a script. Run with python, not bazel.

Usage:
./single_task/run_eval_tasks.py \
    --exp EXP --desc DESC [--tuning_tasks] [--iclr_tasks] [--task TASK] \
    [--tasks TASK1 TASK2 ...]

where EXP is one of the keys in `experiments`,
and DESC is a string description of the set of experiments (such as "v0")

Set only one of these flags:
--tuning_tasks flag only runs tuning tasks.
--iclr_tasks flag only runs the tasks included in the paper.
--regression_tests flag runs tasks which function as regression tests.
--task flag manually selects a single task to run.
--tasks flag takes a custom list of tasks.

Other flags:
--reps N specifies N repetitions per experiment, Default is 25.
--training_replicas R specifies that R workers will be launched to train one
    task (for neural network algorithms). These workers will update a global
    model stored on a parameter server. Defaults to 1. If R > 1, a parameter
    server will also be launched.


Run everything:
exps=( pg-20M pg-topk-20M topk-20M ga-20M rand-20M )
BIN_DIR="single_task"
for exp in "${exps[@]}"
do
  ./$BIN_DIR/run_eval_tasks.py \
      --exp "$exp" --iclr_tasks
done
"""

import argparse
from collections import namedtuple
import subprocess


S = namedtuple('S', ['length'])
default_length = 100


iclr_tasks = [
    'reverse', 'remove-char', 'count-char', 'add', 'bool-logic', 'print-hello',
    'echo-twice', 'echo-thrice', 'copy-reverse', 'zero-cascade', 'cascade',
    'shift-left', 'shift-right', 'riffle', 'unriffle', 'middle-char',
    'remove-last', 'remove-last-two', 'echo-alternating', 'echo-half', 'length',
    'echo-second-seq', 'echo-nth-seq', 'substring', 'divide-2', 'dedup']


regression_test_tasks = ['reverse', 'test-hill-climb']


E = namedtuple(
    'E',
    ['name', 'method_type', 'config', 'simplify', 'batch_size', 'max_npe'])


def make_experiment_settings(name, **kwargs):
  # Unpack experiment info from name.
  def split_last(string, char):
    i = string.rindex(char)
    return string[:i], string[i+1:]
  def si_to_int(si_string):
    return int(
        si_string.upper().replace('K', '0'*3).replace('M', '0'*6)
        .replace('G', '0'*9))
  method_type, max_npe = split_last(name, '-')
  assert method_type
  assert max_npe
  return E(
      name=name, method_type=method_type, max_npe=si_to_int(max_npe), **kwargs)


experiments_set = {
    make_experiment_settings(
        'pg-20M',
        config='entropy_beta=0.05,lr=0.0001,topk_loss_hparam=0.0,topk=0,'
               'pi_loss_hparam=1.0,alpha=0.0',
        simplify=False,
        batch_size=64),
    make_experiment_settings(
        'pg-topk-20M',
        config='entropy_beta=0.01,lr=0.0001,topk_loss_hparam=50.0,topk=10,'
               'pi_loss_hparam=1.0,alpha=0.0',
        simplify=False,
        batch_size=64),
    make_experiment_settings(
        'topk-20M',
        config='entropy_beta=0.01,lr=0.0001,topk_loss_hparam=200.0,topk=10,'
               'pi_loss_hparam=0.0,alpha=0.0',
        simplify=False,
        batch_size=64),
    make_experiment_settings(
        'topk-0ent-20M',
        config='entropy_beta=0.000,lr=0.0001,topk_loss_hparam=200.0,topk=10,'
               'pi_loss_hparam=0.0,alpha=0.0',
        simplify=False,
        batch_size=64),
    make_experiment_settings(
        'ga-20M',
        config='crossover_rate=0.95,mutation_rate=0.15',
        simplify=False,
        batch_size=100),  # Population size.
    make_experiment_settings(
        'rand-20M',
        config='',
        simplify=False,
        batch_size=1),
    make_experiment_settings(
        'simpl-500M',
        config='entropy_beta=0.05,lr=0.0001,topk_loss_hparam=0.5,topk=10,'
               'pi_loss_hparam=1.0,alpha=0.0',
        simplify=True,
        batch_size=64),
}

experiments = {e.name: e for e in experiments_set}


# pylint: disable=redefined-outer-name
def parse_args(extra_args=()):
  """Parse arguments and extract task and experiment info."""
  parser = argparse.ArgumentParser(description='Run all eval tasks.')
  parser.add_argument('--exp', required=True)
  parser.add_argument('--tuning_tasks', action='store_true')
  parser.add_argument('--iclr_tasks', action='store_true')
  parser.add_argument('--regression_tests', action='store_true')
  parser.add_argument('--desc', default='v0')
  parser.add_argument('--reps', default=25)
  parser.add_argument('--task')
  parser.add_argument('--tasks', nargs='+')
  for arg_string, default in extra_args:
    parser.add_argument(arg_string, default=default)
  args = parser.parse_args()

  print('Running experiment: %s' % (args.exp,))
  if args.desc:
    print('Extra description: "%s"' % (args.desc,))
  if args.exp not in experiments:
    raise ValueError('Experiment name is not valid')
  experiment_name = args.exp
  experiment_settings = experiments[experiment_name]
  assert experiment_settings.name == experiment_name

  if args.tasks:
    print('Launching tasks from args: %s' % (args.tasks,))
    tasks = {t: S(length=default_length) for t in args.tasks}
  elif args.task:
    print('Launching single task "%s"' % args.task)
    tasks = {args.task: S(length=default_length)}
  elif args.tuning_tasks:
    print('Only running tuning tasks')
    tasks = {name: S(length=default_length)
             for name in ['reverse-tune', 'remove-char-tune']}
  elif args.iclr_tasks:
    print('Running eval tasks from ICLR paper.')
    tasks = {name: S(length=default_length) for name in iclr_tasks}
  elif args.regression_tests:
    tasks = {name: S(length=default_length) for name in regression_test_tasks}
  print('Tasks: %s' % tasks.keys())

  print('reps = %d' % (int(args.reps),))

  return args, tasks, experiment_settings


def run(command_string):
  subprocess.call(command_string, shell=True)


if __name__ == '__main__':
  LAUNCH_TRAINING_COMMAND = 'single_task/launch_training.sh'
  COMPILE_COMMAND = 'bazel build -c opt single_task:run.par'

  args, tasks, experiment_settings = parse_args(
      extra_args=(('--training_replicas', 1),))

  if experiment_settings.method_type in (
      'pg', 'pg-topk', 'topk', 'topk-0ent', 'simpl'):
    # Runs PG and TopK.

    def make_run_cmd(job_name, task, max_npe, num_reps, code_length,
                     batch_size, do_simplify, custom_config_str):
      """Constructs terminal command for launching NN based algorithms.

      The arguments to this function will be used to create config for the
      experiment.

      Args:
        job_name: Name of the job to launch. Should uniquely identify this
            experiment run.
        task: Name of the coding task to solve.
        max_npe: Maximum number of programs executed. An integer.
        num_reps: Number of times to run the experiment. An integer.
        code_length: Maximum allowed length of synthesized code.
        batch_size: Minibatch size for gradient descent.
        do_simplify: Whether to run the experiment in code simplification mode.
            A bool.
        custom_config_str: Additional config for the model config string.

      Returns:
        The terminal command that launches the specified experiment.
      """
      config = """
        env=c(task='{0}',correct_syntax=False),
        agent=c(
          algorithm='pg',
          policy_lstm_sizes=[35,35],value_lstm_sizes=[35,35],
          grad_clip_threshold=50.0,param_init_factor=0.5,regularizer=0.0,
          softmax_tr=1.0,optimizer='rmsprop',ema_baseline_decay=0.99,
          eos_token={3},{4}),
        timestep_limit={1},batch_size={2}
      """.replace(' ', '').replace('\n', '').format(
          task, code_length, batch_size, do_simplify, custom_config_str)
      num_ps = 0 if args.training_replicas == 1 else 1
      return (
          r'{0} --job_name={1} --config="{2}" --max_npe={3} '
          '--num_repetitions={4} --num_workers={5} --num_ps={6} '
          '--stop_on_success={7}'
          .format(LAUNCH_TRAINING_COMMAND, job_name, config, max_npe, num_reps,
                  args.training_replicas, num_ps, str(not do_simplify).lower()))

  else:
    # Runs GA and Rand.
    assert experiment_settings.method_type in ('ga', 'rand')

    def make_run_cmd(job_name, task, max_npe, num_reps, code_length,
                     batch_size, do_simplify, custom_config_str):
      """Constructs terminal command for launching GA or uniform random search.

      The arguments to this function will be used to create config for the
      experiment.

      Args:
        job_name: Name of the job to launch. Should uniquely identify this
            experiment run.
        task: Name of the coding task to solve.
        max_npe: Maximum number of programs executed. An integer.
        num_reps: Number of times to run the experiment. An integer.
        code_length: Maximum allowed length of synthesized code.
        batch_size: Minibatch size for gradient descent.
        do_simplify: Whether to run the experiment in code simplification mode.
            A bool.
        custom_config_str: Additional config for the model config string.

      Returns:
        The terminal command that launches the specified experiment.
      """
      assert not do_simplify
      if custom_config_str:
        custom_config_str = ',' + custom_config_str
      config = """
        env=c(task='{0}',correct_syntax=False),
        agent=c(
          algorithm='{4}'
          {3}),
        timestep_limit={1},batch_size={2}
      """.replace(' ', '').replace('\n', '').format(
          task, code_length, batch_size, custom_config_str,
          experiment_settings.method_type)
      num_workers = num_reps  # Do each rep in parallel.
      return (
          r'{0} --job_name={1} --config="{2}" --max_npe={3} '
          '--num_repetitions={4} --num_workers={5} --num_ps={6} '
          '--stop_on_success={7}'
          .format(LAUNCH_TRAINING_COMMAND, job_name, config, max_npe, num_reps,
                  num_workers, 0, str(not do_simplify).lower()))

  print('Compiling...')
  run(COMPILE_COMMAND)

  print('Launching %d coding tasks...' % len(tasks))
  for task, task_settings in tasks.iteritems():
    name = 'bf_rl_iclr'
    desc = '{0}.{1}_{2}'.format(args.desc, experiment_settings.name, task)
    job_name = '{}.{}'.format(name, desc)
    print('Job name: %s' % job_name)
    reps = int(args.reps) if not experiment_settings.simplify else 1
    run_cmd = make_run_cmd(
        job_name, task, experiment_settings.max_npe, reps,
        task_settings.length, experiment_settings.batch_size,
        experiment_settings.simplify,
        experiment_settings.config)
    print('Running command:\n' + run_cmd)
    run(run_cmd)

  print('Done.')
# pylint: enable=redefined-outer-name

#This file: results_lib.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Results object manages distributed reading and writing of results to disk."""

import ast
from collections import namedtuple
import os
import re
from six.moves import xrange
import tensorflow as tf


ShardStats = namedtuple(
    'ShardStats',
    ['num_local_reps_completed', 'max_local_reps', 'finished'])


def ge_non_zero(a, b):
  return a >= b and b > 0


def get_shard_id(file_name):
  assert file_name[-4:].lower() == '.txt'
  return int(file_name[file_name.rfind('_') + 1: -4])


class Results(object):
  """Manages reading and writing training results to disk asynchronously.

  Each worker writes to its own file, so that there are no race conditions when
  writing happens. However any worker may read any file, as is the case for
  `read_all`. Writes are expected to be atomic so that workers will never
  read incomplete data, and this is likely to be the case on Unix systems.
  Reading out of date data is fine, as workers calling `read_all` will wait
  until data from every worker has been written before proceeding.
  """
  file_template = 'experiment_results_{0}.txt'
  search_regex = r'^experiment_results_([0-9])+\.txt$'

  def __init__(self, log_dir, shard_id=0):
    """Construct `Results` instance.

    Args:
      log_dir: Where to write results files.
      shard_id: Unique id for this file (i.e. shard). Each worker that will
          be writing results should use a different shard id. If there are
          N shards, each shard should be numbered 0 through N-1.
    """
    # Use different files for workers so that they can write to disk async.
    assert 0 <= shard_id
    self.file_name = self.file_template.format(shard_id)
    self.log_dir = log_dir
    self.results_file = os.path.join(self.log_dir, self.file_name)

  def append(self, metrics):
    """Append results to results list on disk."""
    with tf.gfile.FastGFile(self.results_file, 'a') as writer:
      writer.write(str(metrics) + '\n')

  def read_this_shard(self):
    """Read only from this shard."""
    return self._read_shard(self.results_file)

  def _read_shard(self, results_file):
    """Read only from the given shard file."""
    try:
      with tf.gfile.FastGFile(results_file, 'r') as reader:
        results = [ast.literal_eval(entry) for entry in reader]
    except tf.errors.NotFoundError:
      # No results written to disk yet. Return empty list.
      return []
    return results

  def _get_max_local_reps(self, shard_results):
    """Get maximum number of repetitions the given shard needs to complete.

    Worker working on each shard needs to complete a certain number of runs
    before it finishes. This method will return that number so that we can
    determine which shards are still not done.

    We assume that workers are including a 'max_local_repetitions' value in
    their results, which should be the total number of repetitions it needs to
    run.

    Args:
      shard_results: Dict mapping metric names to values. This should be read
          from a shard on disk.

    Returns:
      Maximum number of repetitions the given shard needs to complete.
    """
    mlrs = [r['max_local_repetitions'] for r in shard_results]
    if not mlrs:
      return 0
    for n in mlrs[1:]:
      assert n == mlrs[0], 'Some reps have different max rep.'
    return mlrs[0]

  def read_all(self, num_shards=None):
    """Read results across all shards, i.e. get global results list.

    Args:
      num_shards: (optional) specifies total number of shards. If the caller
          wants information about which shards are incomplete, provide this
          argument (so that shards which have yet to be created are still
          counted as incomplete shards). Otherwise, no information about
          incomplete shards will be returned.

    Returns:
      aggregate: Global list of results (across all shards).
      shard_stats: List of ShardStats instances, one for each shard. Or None if
          `num_shards` is None.
    """
    try:
      all_children = tf.gfile.ListDirectory(self.log_dir)
    except tf.errors.NotFoundError:
      if num_shards is None:
        return [], None
      return [], [[] for _ in xrange(num_shards)]
    shard_ids = {
        get_shard_id(fname): fname
        for fname in all_children if re.search(self.search_regex, fname)}

    if num_shards is None:
      aggregate = []
      shard_stats = None
      for results_file in shard_ids.values():
        aggregate.extend(self._read_shard(
            os.path.join(self.log_dir, results_file)))
    else:
      results_per_shard = [None] * num_shards
      for shard_id in xrange(num_shards):
        if shard_id in shard_ids:
          results_file = shard_ids[shard_id]
          results_per_shard[shard_id] = self._read_shard(
              os.path.join(self.log_dir, results_file))
        else:
          results_per_shard[shard_id] = []

      # Compute shard stats.
      shard_stats = []
      for shard_results in results_per_shard:
        max_local_reps = self._get_max_local_reps(shard_results)
        shard_stats.append(ShardStats(
            num_local_reps_completed=len(shard_results),
            max_local_reps=max_local_reps,
            finished=ge_non_zero(len(shard_results), max_local_reps)))

      # Compute aggregate.
      aggregate = [
          r for shard_results in results_per_shard for r in shard_results]

    return aggregate, shard_stats

#This file: pg_train.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

r"""Train RL agent on coding tasks."""

import contextlib
import cPickle
import cProfile
import marshal
import os
import time

from absl import flags
from absl import logging
import tensorflow as tf

# internal session lib import

from single_task import data  # brain coder
from single_task import defaults  # brain coder
from single_task import pg_agent as agent_lib  # brain coder
from single_task import results_lib  # brain coder


FLAGS = flags.FLAGS
flags.DEFINE_string(
    'master', '',
    'URL of the TensorFlow master to use.')
flags.DEFINE_integer(
    'ps_tasks', 0,
    'Number of parameter server tasks. Only set to 0 for '
    'single worker training.')
flags.DEFINE_integer(
    'summary_interval', 10,
    'How often to write summaries.')
flags.DEFINE_integer(
    'summary_tasks', 16,
    'If greater than 0 only tasks 0 through summary_tasks - 1 '
    'will write summaries. If 0, all tasks will write '
    'summaries.')
flags.DEFINE_bool(
    'stop_on_success', True,
    'If True, training will stop as soon as a solution is found. '
    'If False, training will continue indefinitely until another '
    'stopping condition is reached.')
flags.DEFINE_bool(
    'do_profiling', False,
    'If True, cProfile profiler will run and results will be '
    'written to logdir. WARNING: Results will not be written if '
    'the code crashes. Make sure it exists successfully.')
flags.DEFINE_integer('model_v', 0, 'Model verbosity level.')
flags.DEFINE_bool(
    'delayed_graph_cleanup', True,
    'If true, container for n-th run will not be reset until the (n+1)-th run '
    'is complete. This greatly reduces the chance that a worker is still '
    'using the n-th container when it is cleared.')


def define_tuner_hparam_space(hparam_space_type):
  """Define tunable hparams for grid search."""
  if hparam_space_type not in ('pg', 'pg-topk', 'topk', 'is'):
    raise ValueError('Hparam space is not valid: "%s"' % hparam_space_type)

  # Discrete hparam space is stored as a dict from hparam name to discrete
  # values.
  hparam_space = {}

  if hparam_space_type in ('pg', 'pg-topk', 'is'):
    # Add a floating point parameter named learning rate.
    hparam_space['lr'] = [1e-5, 1e-4, 1e-3]
    hparam_space['entropy_beta'] = [0.005, 0.01, 0.05, 0.10]
  else:  # 'topk'
    # Add a floating point parameter named learning rate.
    hparam_space['lr'] = [1e-5, 1e-4, 1e-3]
    hparam_space['entropy_beta'] = [0.0, 0.005, 0.01, 0.05, 0.10]

  if hparam_space_type in ('topk', 'pg-topk'):
    # topk tuning will be enabled.
    hparam_space['topk'] = [10]
    hparam_space['topk_loss_hparam'] = [1.0, 10.0, 50.0, 200.0]

  elif hparam_space_type == 'is':
    # importance sampling tuning will be enabled.
    hparam_space['replay_temperature'] = [0.25, 0.5, 1.0, 2.0]
    hparam_space['alpha'] = [0.5, 0.75, 63/64.]

  return hparam_space


def write_hparams_to_config(config, hparams, hparam_space_type):
  """Write hparams given by the tuner into the Config object."""
  if hparam_space_type not in ('pg', 'pg-topk', 'topk', 'is'):
    raise ValueError('Hparam space is not valid: "%s"' % hparam_space_type)

  config.agent.lr = hparams.lr
  config.agent.entropy_beta = hparams.entropy_beta

  if hparam_space_type in ('topk', 'pg-topk'):
    # topk tuning will be enabled.
    config.agent.topk = hparams.topk
    config.agent.topk_loss_hparam = hparams.topk_loss_hparam
  elif hparam_space_type == 'is':
    # importance sampling tuning will be enabled.
    config.agent.replay_temperature = hparams.replay_temperature
    config.agent.alpha = hparams.alpha


def make_initialized_variable(value, name, shape=None, dtype=tf.float32):
  """Create a tf.Variable with a constant initializer.

  Args:
    value: Constant value to initialize the variable with. This is the value
        that the variable starts with.
    name: Name of the variable in the TF graph.
    shape: Shape of the variable. If None, variable will be a scalar.
    dtype: Data type of the variable. Should be a TF dtype. Defaults to
        tf.float32.

  Returns:
    tf.Variable instance.
  """
  if shape is None:
    shape = []
  return tf.get_variable(
      name=name, shape=shape, initializer=tf.constant_initializer(value),
      dtype=dtype, trainable=False)


class AsyncTrainer(object):
  """Manages graph creation and training.

  This async trainer creates a global model on the parameter server, and a local
  model (for this worker). Gradient updates are sent to the global model, and
  the updated weights are synced to the local copy.
  """

  def __init__(self, config, task_id, ps_tasks, num_workers, is_chief=True,
               summary_writer=None,
               dtype=tf.float32,
               summary_interval=1,
               run_number=0,
               logging_dir='/tmp', model_v=0):
    self.config = config
    self.data_manager = data.DataManager(
        config, run_number=run_number,
        do_code_simplification=not FLAGS.stop_on_success)
    self.task_id = task_id
    self.ps_tasks = ps_tasks
    self.is_chief = is_chief
    if ps_tasks == 0:
      assert task_id == 0, 'No parameter servers specified. Expecting 1 task.'
      assert num_workers == 1, (
          'No parameter servers specified. Expecting 1 task.')
      worker_device = '/job:localhost/replica:%d/task:0/cpu:0' % task_id
      # worker_device = '/cpu:0'
      # ps_device = '/cpu:0'
    else:
      assert num_workers > 0, 'There must be at least 1 training worker.'
      worker_device = '/job:worker/replica:%d/task:0/cpu:0' % task_id
      # ps_device = '/job:ps/replica:0/task:0/cpu:0'
    logging.info('worker_device: %s', worker_device)

    logging_file = os.path.join(
        logging_dir, 'solutions_%d.txt' % task_id)
    experience_replay_file = os.path.join(
        logging_dir, 'replay_buffer_%d.pickle' % task_id)
    self.topk_file = os.path.join(
        logging_dir, 'topk_buffer_%d.pickle' % task_id)

    tf.get_variable_scope().set_use_resource(True)

    # global model
    with tf.device(tf.train.replica_device_setter(ps_tasks,
                                                  ps_device='/job:ps/replica:0',
                                                  worker_device=worker_device)):
      with tf.variable_scope('global'):
        global_model = agent_lib.LMAgent(config, dtype=dtype, is_local=False)
        global_params_dict = {p.name: p
                              for p in global_model.sync_variables}
        self.global_model = global_model
        self.global_step = make_initialized_variable(
            0, 'global_step', dtype=tf.int64)

        self.global_best_reward = make_initialized_variable(
            -10.0, 'global_best_reward', dtype=tf.float64)
        self.is_best_model = make_initialized_variable(
            False, 'is_best_model', dtype=tf.bool)
        self.reset_is_best_model = self.is_best_model.assign(False)
        self.global_best_reward_placeholder = tf.placeholder(
            tf.float64, [], name='global_best_reward_placeholder')
        self.assign_global_best_reward_op = tf.group(
            self.global_best_reward.assign(
                self.global_best_reward_placeholder),
            self.is_best_model.assign(True))
        def assign_global_best_reward_fn(session, reward):
          reward = round(reward, 10)
          best_reward = round(session.run(self.global_best_reward), 10)
          is_best = reward > best_reward
          if is_best:
            session.run(self.assign_global_best_reward_op,
                        {self.global_best_reward_placeholder: reward})
          return is_best
        self.assign_global_best_reward_fn = assign_global_best_reward_fn

        # Any worker will set to true when it finds a solution.
        self.found_solution_flag = make_initialized_variable(
            False, 'found_solution_flag', dtype=tf.bool)
        self.found_solution_op = self.found_solution_flag.assign(True)

        self.run_number = make_initialized_variable(
            run_number, 'run_number', dtype=tf.int32)

        # Store a solution when found.
        self.code_solution_variable = tf.get_variable(
            'code_solution', [], tf.string,
            initializer=tf.constant_initializer(''))
        self.code_solution_ph = tf.placeholder(
            tf.string, [], name='code_solution_ph')
        self.code_solution_assign_op = self.code_solution_variable.assign(
            self.code_solution_ph)
        def assign_code_solution_fn(session, code_solution_string):
          session.run(self.code_solution_assign_op,
                      {self.code_solution_ph: code_solution_string})
        self.assign_code_solution_fn = assign_code_solution_fn

        # Count all programs sampled from policy. This does not include
        # programs sampled from replay buffer.
        # This equals NPE (number of programs executed). Only programs sampled
        # from the policy need to be executed.
        self.program_count = make_initialized_variable(
            0, 'program_count', dtype=tf.int64)

    # local model
    with tf.device(worker_device):
      with tf.variable_scope('local'):
        self.model = model = agent_lib.LMAgent(
            config,
            task_id=task_id,
            logging_file=logging_file,
            experience_replay_file=experience_replay_file,
            dtype=dtype,
            global_best_reward_fn=self.assign_global_best_reward_fn,
            found_solution_op=self.found_solution_op,
            assign_code_solution_fn=self.assign_code_solution_fn,
            program_count=self.program_count,
            stop_on_success=FLAGS.stop_on_success,
            verbose_level=model_v)
        local_params = model.trainable_variables
        local_params_dict = {p.name: p for p in local_params}

    # Pull global params to local model.
    def _global_to_local_scope(name):
      assert name.startswith('global/')
      return 'local' + name[6:]
    sync_dict = {
        local_params_dict[_global_to_local_scope(p_name)]: p
        for p_name, p in global_params_dict.items()}
    self.sync_op = tf.group(*[v_local.assign(v_global)
                              for v_local, v_global
                              in sync_dict.items()])

    # Pair local gradients with global params.
    grad_var_dict = {
        gradient: sync_dict[local_var]
        for local_var, gradient in model.gradients_dict.items()}

    # local model
    model.make_summary_ops()  # Don't put summaries under 'local' scope.
    with tf.variable_scope('local'):
      self.train_op = model.optimizer.apply_gradients(
          grad_var_dict.items(), global_step=self.global_step)
      self.local_init_op = tf.variables_initializer(
          tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES,
                            tf.get_variable_scope().name))

    self.local_step = 0
    self.last_summary_time = time.time()
    self.summary_interval = summary_interval
    self.summary_writer = summary_writer
    self.cached_global_step = -1
    self.cached_global_npe = -1

    logging.info('summary_interval: %d', self.summary_interval)

    # Load top-k buffer.
    if self.model.top_episodes is not None and tf.gfile.Exists(self.topk_file):
      try:
        with tf.gfile.FastGFile(self.topk_file, 'r') as f:
          self.model.top_episodes = cPickle.loads(f.read())
        logging.info(
            'Loaded top-k buffer from disk with %d items. Location: "%s"',
            len(self.model.top_episodes), self.topk_file)
      except (cPickle.UnpicklingError, EOFError) as e:
        logging.warn(
            'Failed to load existing top-k buffer from disk. Removing bad file.'
            '\nLocation: "%s"\nException: %s', self.topk_file, str(e))
        tf.gfile.Remove(self.topk_file)

  def initialize(self, session):
    """Run initialization ops."""
    session.run(self.local_init_op)
    session.run(self.sync_op)
    self.cached_global_step, self.cached_global_npe = session.run(
        [self.global_step, self.program_count])

  def update_global_model(self, session):
    """Run an update step.

    1) Asynchronously copy global weights to local model.
    2) Call into local model's update_step method, which does the following:
        a) Sample batch of programs from policy.
        b) Compute rewards.
        c) Compute gradients and update the global model asynchronously.
    3) Write tensorboard summaries to disk.

    Args:
      session: tf.Session instance.
    """
    session.run(self.sync_op)  # Copy weights from global to local.

    with session.as_default():
      result = self.model.update_step(
          session, self.data_manager.sample_rl_batch(), self.train_op,
          self.global_step)
      global_step = result.global_step
      global_npe = result.global_npe
      summaries = result.summaries_list
    self.cached_global_step = global_step
    self.cached_global_npe = global_npe
    self.local_step += 1

    if self.summary_writer and self.local_step % self.summary_interval == 0:
      if not isinstance(summaries, (tuple, list)):
        summaries = [summaries]
      summaries.append(self._local_step_summary())
      if self.is_chief:
        (global_best_reward,
         found_solution_flag,
         program_count) = session.run(
             [self.global_best_reward,
              self.found_solution_flag,
              self.program_count])
        summaries.append(
            tf.Summary(
                value=[tf.Summary.Value(
                    tag='model/best_reward',
                    simple_value=global_best_reward)]))
        summaries.append(
            tf.Summary(
                value=[tf.Summary.Value(
                    tag='model/solution_found',
                    simple_value=int(found_solution_flag))]))
        summaries.append(
            tf.Summary(
                value=[tf.Summary.Value(
                    tag='model/program_count',
                    simple_value=program_count)]))
      for s in summaries:
        self.summary_writer.add_summary(s, global_step)
      self.last_summary_time = time.time()

  def _local_step_summary(self):
    """Compute number of local steps per time increment."""
    dt = time.time() - self.last_summary_time
    steps_per_time = self.summary_interval / float(dt)
    return tf.Summary(value=[
        tf.Summary.Value(
            tag='local_step/per_sec',
            simple_value=steps_per_time),
        tf.Summary.Value(
            tag='local_step/step',
            simple_value=self.local_step)])

  def maybe_save_best_model(self, session, saver, checkpoint_file):
    """Check if this model got the highest reward and save to disk if so."""
    if self.is_chief and session.run(self.is_best_model):
      logging.info('Saving best model to "%s"', checkpoint_file)
      saver.save(session, checkpoint_file)
      session.run(self.reset_is_best_model)

  def save_replay_buffer(self):
    """Save replay buffer to disk.

    Call this periodically so that training can recover if jobs go down.
    """
    if self.model.experience_replay is not None:
      logging.info('Saving experience replay buffer to "%s".',
                   self.model.experience_replay.save_file)
      self.model.experience_replay.incremental_save(True)

  def delete_replay_buffer(self):
    """Delete replay buffer from disk.

    Call this at the end of training to clean up. Replay buffer can get very
    large.
    """
    if self.model.experience_replay is not None:
      logging.info('Deleting experience replay buffer at "%s".',
                   self.model.experience_replay.save_file)
      tf.gfile.Remove(self.model.experience_replay.save_file)

  def save_topk_buffer(self):
    """Save top-k buffer to disk.

    Call this periodically so that training can recover if jobs go down.
    """
    if self.model.top_episodes is not None:
      logging.info('Saving top-k buffer to "%s".', self.topk_file)
      # Overwrite previous data each time.
      with tf.gfile.FastGFile(self.topk_file, 'w') as f:
        f.write(cPickle.dumps(self.model.top_episodes))


@contextlib.contextmanager
def managed_session(sv, master='', config=None,
                    start_standard_services=True,
                    close_summary_writer=True,
                    max_wait_secs=7200):
  # Same as Supervisor.managed_session, but with configurable timeout.
  try:
    sess = sv.prepare_or_wait_for_session(
        master=master, config=config,
        start_standard_services=start_standard_services,
        max_wait_secs=max_wait_secs)
    yield sess
  except tf.errors.DeadlineExceededError:
    raise
  except Exception as e:  # pylint: disable=broad-except
    sv.request_stop(e)
  finally:
    try:
      # Request all the threads to stop and wait for them to do so.  Any
      # exception raised by the threads is raised again from stop().
      # Passing stop_grace_period_secs is for blocked enqueue/dequeue
      # threads which are not checking for `should_stop()`.  They
      # will be stopped when we close the session further down.
      sv.stop(close_summary_writer=close_summary_writer)
    finally:
      # Close the session to finish up all pending calls.  We do not care
      # about exceptions raised when closing.  This takes care of
      # blocked enqueue/dequeue calls.
      try:
        sess.close()
      except Exception:  # pylint: disable=broad-except
        # Silently ignore exceptions raised by close().
        pass


def train(config, is_chief, tuner=None, run_dir=None, run_number=0,
          results_writer=None):
  """Run training loop.

  Args:
    config: config_lib.Config instance containing global config (agent and env).
    is_chief: True if this worker is chief. Chief worker manages writing some
        data to disk and initialization of the global model.
    tuner: A tuner instance. If not tuning, leave as None.
    run_dir: Directory where all data for this run will be written. If None,
        run_dir = FLAGS.logdir. Set this argument when doing multiple runs.
    run_number: Which run is this.
    results_writer: Managest writing training results to disk. Results are a
        dict of metric names and values.

  Returns:
    The trainer object used to run training updates.
  """
  logging.info('Will run asynchronous training.')

  if run_dir is None:
    run_dir = FLAGS.logdir
  train_dir = os.path.join(run_dir, 'train')
  best_model_checkpoint = os.path.join(train_dir, 'best.ckpt')
  events_dir = '%s/events_%d' % (run_dir, FLAGS.task_id)
  logging.info('Events directory: %s', events_dir)

  logging_dir = os.path.join(run_dir, 'logs')
  if not tf.gfile.Exists(logging_dir):
    tf.gfile.MakeDirs(logging_dir)
  status_file = os.path.join(logging_dir, 'status.txt')

  if FLAGS.summary_tasks and FLAGS.task_id < FLAGS.summary_tasks:
    summary_writer = tf.summary.FileWriter(events_dir)
  else:
    summary_writer = None

  # Only profile task 0.
  if FLAGS.do_profiling:
    logging.info('Profiling enabled')
    profiler = cProfile.Profile()
    profiler.enable()
  else:
    profiler = None

  trainer = AsyncTrainer(
      config, FLAGS.task_id, FLAGS.ps_tasks, FLAGS.num_workers,
      is_chief=is_chief,
      summary_interval=FLAGS.summary_interval,
      summary_writer=summary_writer,
      logging_dir=logging_dir,
      run_number=run_number,
      model_v=FLAGS.model_v)

  variables_to_save = [v for v in tf.global_variables()
                       if v.name.startswith('global')]
  global_init_op = tf.variables_initializer(variables_to_save)
  saver = tf.train.Saver(variables_to_save)

  var_list = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,
                               tf.get_variable_scope().name)
  logging.info('Trainable vars:')
  for v in var_list:
    logging.info('  %s, %s, %s', v.name, v.device, v.get_shape())

  logging.info('All vars:')
  for v in tf.global_variables():
    logging.info('  %s, %s, %s', v.name, v.device, v.get_shape())

  def init_fn(unused_sess):
    logging.info('No checkpoint found. Initialized global params.')

  sv = tf.train.Supervisor(is_chief=is_chief,
                           logdir=train_dir,
                           saver=saver,
                           summary_op=None,
                           init_op=global_init_op,
                           init_fn=init_fn,
                           summary_writer=summary_writer,
                           ready_op=tf.report_uninitialized_variables(
                               variables_to_save),
                           ready_for_local_init_op=None,
                           global_step=trainer.global_step,
                           save_model_secs=30,
                           save_summaries_secs=30)

  # Add a thread that periodically checks if this Trial should stop
  # based on an early stopping policy.
  if tuner:
    sv.Loop(60, tuner.check_for_stop, (sv.coord,))

  last_replay_save_time = time.time()

  global_step = -1
  logging.info(
      'Starting session. '
      'If this hangs, we\'re mostly likely waiting to connect '
      'to the parameter server. One common cause is that the parameter '
      'server DNS name isn\'t resolving yet, or is misspecified.')
  should_retry = True
  supervisor_deadline_exceeded = False
  while should_retry:
    try:
      with managed_session(
          sv, FLAGS.master, max_wait_secs=60) as session, session.as_default():
        should_retry = False
        do_training = True

        try:
          trainer.initialize(session)
          if session.run(trainer.run_number) != run_number:
            # If we loaded existing model from disk, and the saved run number is
            # different, throw an exception.
            raise RuntimeError(
                'Expecting to be on run %d, but is actually on run %d. '
                'run_dir: "%s"'
                % (run_number, session.run(trainer.run_number), run_dir))
          global_step = trainer.cached_global_step
          logging.info('Starting training at step=%d', global_step)
          while do_training:
            trainer.update_global_model(session)

            if is_chief:
              trainer.maybe_save_best_model(
                  session, saver, best_model_checkpoint)
            global_step = trainer.cached_global_step
            global_npe = trainer.cached_global_npe

            if time.time() - last_replay_save_time >= 30:
              trainer.save_replay_buffer()
              trainer.save_topk_buffer()
              last_replay_save_time = time.time()

            # Stopping conditions.
            if tuner and tuner.should_trial_stop():
              logging.info('Tuner requested early stopping. Finishing.')
              do_training = False
            if is_chief and FLAGS.stop_on_success:
              found_solution = session.run(trainer.found_solution_flag)
              if found_solution:
                do_training = False
                logging.info('Solution found. Finishing.')
            if FLAGS.max_npe and global_npe >= FLAGS.max_npe:
              # Max NPE (number of programs executed) reached.
              logging.info('Max NPE reached. Finishing.')
              do_training = False
            if sv.should_stop():
              logging.info('Supervisor issued stop. Finishing.')
              do_training = False

        except tf.errors.NotFoundError:
          # Catch "Error while reading resource variable".
          # The chief worker likely destroyed the container, so do not retry.
          logging.info('Caught NotFoundError. Quitting.')
          do_training = False
          should_retry = False
          break
        except tf.errors.InternalError as e:
          # Catch "Invalid variable reference."
          if str(e).startswith('Invalid variable reference.'):
            # The chief worker likely destroyed the container, so do not
            # retry.
            logging.info(
                'Caught "InternalError: Invalid variable reference.". '
                'Quitting.')
            do_training = False
            should_retry = False
            break
          else:
            # Pass exception through.
            raise

        # Exited training loop. Write results to disk.
        if is_chief and results_writer:
          assert not should_retry
          with tf.gfile.FastGFile(status_file, 'w') as f:
            f.write('done')
          (program_count,
           found_solution,
           code_solution,
           best_reward,
           global_step) = session.run(
               [trainer.program_count,
                trainer.found_solution_flag,
                trainer.code_solution_variable,
                trainer.global_best_reward,
                trainer.global_step])
          results_dict = {
              'max_npe': FLAGS.max_npe,
              'batch_size': config.batch_size,
              'max_batches': FLAGS.max_npe // config.batch_size,
              'npe': program_count,
              'max_global_repetitions': FLAGS.num_repetitions,
              'max_local_repetitions': FLAGS.num_repetitions,
              'code_solution': code_solution,
              'best_reward': best_reward,
              'num_batches': global_step,
              'found_solution': found_solution,
              'task': trainer.data_manager.task_name,
              'global_rep': run_number}
          logging.info('results_dict: %s', results_dict)
          results_writer.append(results_dict)

    except tf.errors.AbortedError:
      # Catch "Graph handle is not found" error due to preempted jobs.
      logging.info('Caught AbortedError. Retying.')
      should_retry = True
    except tf.errors.DeadlineExceededError:
      supervisor_deadline_exceeded = True
      should_retry = False

  if is_chief:
    logging.info('This is chief worker. Stopping all workers.')
    sv.stop()

  if supervisor_deadline_exceeded:
    logging.info('Supervisor timed out. Quitting.')
  else:
    logging.info('Reached %s steps. Worker stopped.', global_step)

  # Dump profiling.
  """
  How to use profiling data.

  Download the profiler dump to your local machine, say to PROF_FILE_PATH.
  In a separate script, run something like the following:

  import pstats
  p = pstats.Stats(PROF_FILE_PATH)
  p.strip_dirs().sort_stats('cumtime').print_stats()

  This will sort by 'cumtime', which "is the cumulative time spent in this and
  all subfunctions (from invocation till exit)."
  https://docs.python.org/2/library/profile.html#instant-user-s-manual
  """  # pylint: disable=pointless-string-statement
  if profiler:
    prof_file = os.path.join(run_dir, 'task_%d.prof' % FLAGS.task_id)
    logging.info('Done profiling.\nDumping to "%s".', prof_file)
    profiler.create_stats()
    with tf.gfile.Open(prof_file, 'w') as f:
      f.write(marshal.dumps(profiler.stats))

  return trainer


def run_training(config=None, tuner=None, logdir=None, trial_name=None,
                 is_chief=True):
  """Do all training runs.

  This is the top level training function for policy gradient based models.
  Run this from the main function.

  Args:
    config: config_lib.Config instance containing global config (agent and
        environment hparams). If None, config will be parsed from FLAGS.config.
    tuner: A tuner instance. Leave as None if not tuning.
    logdir: Parent directory where all data from all runs will be written. If
        None, FLAGS.logdir will be used.
    trial_name: If tuning, set this to a unique string that identifies this
        trial. If `tuner` is not None, this also must be set.
    is_chief: True if this worker is the chief.

  Returns:
    List of results dicts which were written to disk. Each training run gets a
    results dict. Results dict contains metrics, i.e. (name, value) pairs which
    give information about the training run.

  Raises:
    ValueError: If results dicts read from disk contain invalid data.
  """
  if not config:
    # If custom config is not given, get it from flags.
    config = defaults.default_config_with_updates(FLAGS.config)
  if not logdir:
    logdir = FLAGS.logdir
  if not tf.gfile.Exists(logdir):
    tf.gfile.MakeDirs(logdir)
  assert FLAGS.num_repetitions > 0
  results = results_lib.Results(logdir)
  results_list, _ = results.read_all()

  logging.info('Starting experiment. Directory: "%s"', logdir)

  if results_list:
    if results_list[0]['max_npe'] != FLAGS.max_npe:
      raise ValueError(
          'Cannot resume training. Max-NPE changed. Was %s, now %s',
          results_list[0]['max_npe'], FLAGS.max_npe)
    if results_list[0]['max_global_repetitions'] != FLAGS.num_repetitions:
      raise ValueError(
          'Cannot resume training. Number of repetitions changed. Was %s, '
          'now %s',
          results_list[0]['max_global_repetitions'],
          FLAGS.num_repetitions)

  while len(results_list) < FLAGS.num_repetitions:
    run_number = len(results_list)
    rep_container_name = trial_name if trial_name else 'container'
    if FLAGS.num_repetitions > 1:
      rep_dir = os.path.join(logdir, 'run_%d' % run_number)
      rep_container_name = rep_container_name + '_run_' + str(run_number)
    else:
      rep_dir = logdir

    logging.info(
        'Starting repetition %d (%d out of %d)', run_number, run_number + 1,
        FLAGS.num_repetitions)

    # Train will write result to disk.
    with tf.container(rep_container_name):
      trainer = train(config, is_chief, tuner, rep_dir, run_number, results)
    logging.info('Done training.')

    if is_chief:
      # Destroy current container immediately (clears current graph).
      logging.info('Clearing shared variables.')
      tf.Session.reset(FLAGS.master, containers=[rep_container_name])
      logging.info('Shared variables cleared.')

      # Delete replay buffer on disk.
      assert trainer
      trainer.delete_replay_buffer()
    else:
      # Give chief worker time to clean up.
      sleep_sec = 30.0
      logging.info('Sleeping for %s sec.', sleep_sec)
      time.sleep(sleep_sec)
    tf.reset_default_graph()
    logging.info('Default graph reset.')

    # Expecting that train wrote new result to disk before returning.
    results_list, _ = results.read_all()
  return results_list

#This file: pg_train_test.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Tests for pg_train.

These tests excersize code paths available through configuration options.
Training will be run for just a few steps with the goal being to check that
nothing crashes.
"""

from absl import flags
import tensorflow as tf

from single_task import defaults  # brain coder
from single_task import run  # brain coder

FLAGS = flags.FLAGS


class TrainTest(tf.test.TestCase):

  def RunTrainingSteps(self, config_string, num_steps=10):
    """Run a few training steps with the given config.

    Just check that nothing crashes.

    Args:
      config_string: Config encoded in a string. See
          $REPO_PATH/common/config_lib.py
      num_steps: Number of training steps to run. Defaults to 10.
    """
    config = defaults.default_config_with_updates(config_string)
    FLAGS.master = ''
    FLAGS.max_npe = num_steps * config.batch_size
    FLAGS.summary_interval = 1
    FLAGS.logdir = tf.test.get_temp_dir()
    FLAGS.config = config_string
    tf.reset_default_graph()
    run.main(None)

  def testVanillaPolicyGradient(self):
    self.RunTrainingSteps(
        'env=c(task="reverse"),'
        'agent=c(algorithm="pg"),'
        'timestep_limit=90,batch_size=64')

  def testVanillaPolicyGradient_VariableLengthSequences(self):
    self.RunTrainingSteps(
        'env=c(task="reverse"),'
        'agent=c(algorithm="pg",eos_token=False),'
        'timestep_limit=90,batch_size=64')

  def testVanillaActorCritic(self):
    self.RunTrainingSteps(
        'env=c(task="reverse"),'
        'agent=c(algorithm="pg",ema_baseline_decay=0.0),'
        'timestep_limit=90,batch_size=64')

  def testPolicyGradientWithTopK(self):
    self.RunTrainingSteps(
        'env=c(task="reverse"),'
        'agent=c(algorithm="pg",topk_loss_hparam=1.0,topk=10),'
        'timestep_limit=90,batch_size=64')

  def testVanillaActorCriticWithTopK(self):
    self.RunTrainingSteps(
        'env=c(task="reverse"),'
        'agent=c(algorithm="pg",ema_baseline_decay=0.0,topk_loss_hparam=1.0,'
        'topk=10),'
        'timestep_limit=90,batch_size=64')

  def testPolicyGradientWithTopK_VariableLengthSequences(self):
    self.RunTrainingSteps(
        'env=c(task="reverse"),'
        'agent=c(algorithm="pg",topk_loss_hparam=1.0,topk=10,eos_token=False),'
        'timestep_limit=90,batch_size=64')

  def testPolicyGradientWithImportanceSampling(self):
    self.RunTrainingSteps(
        'env=c(task="reverse"),'
        'agent=c(algorithm="pg",alpha=0.5),'
        'timestep_limit=90,batch_size=64')


if __name__ == '__main__':
  tf.test.main()

#This file: ga_lib.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Genetic algorithm for BF tasks.

Inspired by https://github.com/primaryobjects/AI-Programmer.
GA function code borrowed from https://github.com/DEAP/deap.
"""

from collections import namedtuple
import random

from absl import flags
from absl import logging
import numpy as np
from six.moves import xrange

from common import bf  # brain coder
from common import utils  # brain coder
from single_task import misc  # brain coder

FLAGS = flags.FLAGS

# Saving reward of previous programs saves computation if a program appears
# again.
USE_REWARD_CACHE = True  # Disable this if GA is using up too much memory.
GENES = bf.CHARS
MAX_PROGRAM_STEPS = 500
STEP_BONUS = True

ALPHANUM_CHARS = (
    ['_'] +
    [chr(ord('a') + i_) for i_ in range(26)] +
    [chr(ord('A') + i_) for i_ in range(26)] +
    [chr(ord('0') + i_) for i_ in range(10)])

Result = namedtuple(
    'Result',
    ['reward', 'inputs', 'code_outputs', 'target_outputs', 'type_in',
     'type_out', 'base', 'correct'])


class IOType(object):
  string = 'string'
  integer = 'integer'


class CustomType(object):

  def __init__(self, to_str_fn):
    self.to_str_fn = to_str_fn

  def __call__(self, obj):
    return self.to_str_fn(obj)


def tokens_list_repr(tokens, repr_type, base):
  """Make human readable representation of program IO."""
  if isinstance(repr_type, CustomType):
    return repr_type(tokens)
  elif repr_type == IOType.string:
    chars = (
        [ALPHANUM_CHARS[t] for t in tokens] if base < len(ALPHANUM_CHARS)
        else [chr(t) for t in tokens])
    return ''.join(chars)
  elif repr_type == IOType.integer:
    return str(tokens)
  raise ValueError('No such representation type "%s"', repr_type)


def io_repr(result):
  """Make human readable representation of test cases."""
  inputs = ','.join(
      tokens_list_repr(tokens, result.type_in, result.base)
      for tokens in result.inputs)
  code_outputs = ','.join(
      tokens_list_repr(tokens, result.type_out, result.base)
      for tokens in result.code_outputs)
  target_outputs = ','.join(
      tokens_list_repr(tokens, result.type_out, result.base)
      for tokens in result.target_outputs)
  return inputs, target_outputs, code_outputs


def make_task_eval_fn(task_manager):
  """Returns a wrapper that converts an RL task into a GA task.

  Args:
    task_manager: Is a task manager object from code_tasks.py

  Returns:
    A function that takes as input a single list of a code chars, and outputs
    a Result namedtuple instance containing the reward and information about
    code execution.
  """
  def to_data_list(single_or_tuple):
    if isinstance(single_or_tuple, misc.IOTuple):
      return list(single_or_tuple)
    return [single_or_tuple]

  def to_ga_type(rl_type):
    if rl_type == misc.IOType.string:
      return IOType.string
    return IOType.integer

  # Wrapper function.
  def evalbf(bf_chars):
    result = task_manager._score_code(''.join(bf_chars))
    reward = sum(result.episode_rewards)
    correct = result.reason == 'correct'
    return Result(
        reward=reward,
        inputs=to_data_list(result.input_case),
        code_outputs=to_data_list(result.code_output),
        target_outputs=to_data_list(result.correct_output),
        type_in=to_ga_type(result.input_type),
        type_out=to_ga_type(result.output_type),
        correct=correct,
        base=task_manager.task.base)

  return evalbf


def debug_str(individual, task_eval_fn):
  res = task_eval_fn(individual)
  input_str, target_output_str, code_output_str = io_repr(res)
  return (
      ''.join(individual) +
      ' | ' + input_str +
      ' | ' + target_output_str +
      ' | ' + code_output_str +
      ' | ' + str(res.reward) +
      ' | ' + str(res.correct))


def mutate_single(code_tokens, mutation_rate):
  """Mutate a single code string.

  Args:
    code_tokens: A string/list/Individual of BF code chars. Must end with EOS
        symbol '_'.
    mutation_rate: Float between 0 and 1 which sets the probability of each char
        being mutated.

  Returns:
    An Individual instance containing the mutated code string.

  Raises:
    ValueError: If `code_tokens` does not end with EOS symbol.
  """
  if len(code_tokens) <= 1:
    return code_tokens
  if code_tokens[-1] == '_':
    # Do this check to ensure that the code strings have not been corrupted.
    raise ValueError('`code_tokens` must end with EOS symbol.')
  else:
    cs = Individual(code_tokens)
    eos = []
  mutated = False
  for pos in range(len(cs)):
    if random.random() < mutation_rate:
      mutated = True
      new_char = GENES[random.randrange(len(GENES))]
      x = random.random()
      if x < 0.25 and pos != 0 and pos != len(cs) - 1:
        # Insertion mutation.
        if random.random() < 0.50:
          # Shift up.
          cs = cs[:pos] + [new_char] + cs[pos:-1]
        else:
          # Shift down.
          cs = cs[1:pos] + [new_char] + cs[pos:]
      elif x < 0.50:
        # Deletion mutation.
        if random.random() < 0.50:
          # Shift down.
          cs = cs[:pos] + cs[pos + 1:] + [new_char]
        else:
          # Shift up.
          cs = [new_char] + cs[:pos] + cs[pos + 1:]
      elif x < 0.75:
        # Shift rotate mutation (position invariant).
        if random.random() < 0.50:
          # Shift down.
          cs = cs[1:] + [cs[0]]
        else:
          # Shift up.
          cs = [cs[-1]] + cs[:-1]
      else:
        # Replacement mutation.
        cs = cs[:pos] + [new_char] + cs[pos + 1:]
  assert len(cs) + len(eos) == len(code_tokens)
  if mutated:
    return Individual(cs + eos)
  else:
    return Individual(code_tokens)


def crossover(parent1, parent2):
  """Performs crossover mating between two code strings.

  Crossover mating is where a random position is selected, and the chars
  after that point are swapped. The resulting new code strings are returned.

  Args:
    parent1: First code string.
    parent2: Second code string.

  Returns:
    A 2-tuple of children, i.e. the resulting code strings after swapping.
  """
  max_parent, min_parent = (
      (parent1, parent2) if len(parent1) > len(parent2)
      else (parent2, parent1))
  pos = random.randrange(len(max_parent))
  if pos >= len(min_parent):
    child1 = max_parent[:pos]
    child2 = min_parent + max_parent[pos:]
  else:
    child1 = max_parent[:pos] + min_parent[pos:]
    child2 = min_parent[:pos] + max_parent[pos:]
  return Individual(child1), Individual(child2)


def _make_even(n):
  """Return largest even integer less than or equal to `n`."""
  return (n >> 1) << 1


def mutate_and_crossover(population, mutation_rate, crossover_rate):
  """Take a generational step over a population.

  Transforms population of parents into population of children (of the same
  size) via crossover mating and then mutation on the resulting children.

  Args:
    population: Parent population. A list of Individual objects.
    mutation_rate: Probability of mutation. See `mutate_single`.
    crossover_rate: Probability that two parents will mate.

  Returns:
    Child population. A list of Individual objects.
  """
  children = [None] * len(population)
  for i in xrange(0, _make_even(len(population)), 2):
    p1 = population[i]
    p2 = population[i + 1]
    if random.random() < crossover_rate:
      p1, p2 = crossover(p1, p2)
    c1 = mutate_single(p1, mutation_rate)
    c2 = mutate_single(p2, mutation_rate)
    children[i] = c1
    children[i + 1] = c2
  if children[-1] is None:
    children[-1] = population[-1]
  return children


def ga_loop(population, cxpb, mutpb, ngen, task_eval_fn, halloffame=None,
            checkpoint_writer=None):
  """A bare bones genetic algorithm.

  Similar to chapter 7 of Back, Fogel and Michalewicz, "Evolutionary
  Computation 1 : Basic Algorithms and Operators", 2000.

  Args:
    population: A list of individuals.
    cxpb: The probability of mating two individuals.
    mutpb: The probability of mutating a gene.
    ngen: The number of generation. Unlimited if zero.
    task_eval_fn: A python function which maps an Individual to a Result
        namedtuple.
    halloffame: (optional) a utils.MaxUniquePriorityQueue object that will be
        used to aggregate the best individuals found during search.
    checkpoint_writer: (optional) an object that can save and load populations.
        Needs to have `write`, `load`, and `has_checkpoint` methods. Used to
        periodically save progress. In event of a restart, the population will
        be loaded from disk.

  Returns:
    GaResult namedtuple instance. This contains information about the GA run,
    including the resulting population, best reward (fitness) obtained, and
    the best code string found.
  """

  has_checkpoint = False
  if checkpoint_writer and checkpoint_writer.has_checkpoint():
    try:
      gen, population, halloffame = checkpoint_writer.load()
    except EOFError:  # Data was corrupted. Start over.
      pass
    else:
      has_checkpoint = True
      logging.info(
          'Loaded population from checkpoint. Starting at generation %d', gen)

      # Evaluate the individuals with an invalid fitness
      invalid_ind = [ind for ind in population if not ind.fitness.valid]
      for ind in invalid_ind:
        ind.fitness.values = task_eval_fn(ind).reward,
      for _, ind in halloffame.iter_in_order():
        ind.fitness.values = task_eval_fn(ind).reward,

  if not has_checkpoint:
    # Evaluate the individuals with an invalid fitness
    invalid_ind = [ind for ind in population if not ind.fitness.valid]
    for ind in invalid_ind:
      ind.fitness.values = task_eval_fn(ind).reward,

    if halloffame is not None:
      for ind in population:
        halloffame.push(ind.fitness.values, tuple(ind), ind)

    logging.info('Initialized new population.')

    gen = 1

  pop_size = len(population)
  program_reward_cache = {} if USE_REWARD_CACHE else None

  # Begin the generational process
  while ngen == 0 or gen <= ngen:
    # Select the next generation individuals
    offspring = roulette_selection(population, pop_size - len(halloffame))

    # Vary the pool of individuals
    # offspring = varAnd(offspring, toolbox, cxpb, mutpb)
    offspring = mutate_and_crossover(
        offspring, mutation_rate=mutpb, crossover_rate=cxpb)

    # Evaluate the individuals with an invalid fitness
    invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
    for ind in invalid_ind:
      str_repr = ''.join(ind)
      if program_reward_cache is not None and str_repr in program_reward_cache:
        ind.fitness.values = (program_reward_cache[str_repr],)
      else:
        eval_result = task_eval_fn(ind)
        ind.fitness.values = (eval_result.reward,)
        if program_reward_cache is not None:
          program_reward_cache[str_repr] = eval_result.reward

    # Replace the current population by the offspring
    population = list(offspring)

    # Update the hall of fame with the generated individuals
    if halloffame is not None:
      for ind in population:
        halloffame.push(ind.fitness.values, tuple(ind), ind)

    # elitism
    population.extend([ind for _, ind in halloffame.iter_in_order()])

    if gen % 100 == 0:
      top_code = '\n'.join([debug_str(ind, task_eval_fn)
                            for ind in topk(population, k=4)])
      logging.info('gen: %d\nNPE: %d\n%s\n\n', gen, gen * pop_size, top_code)

      best_code = ''.join(halloffame.get_max()[1])
      res = task_eval_fn(best_code)

      # Write population and hall-of-fame to disk.
      if checkpoint_writer:
        checkpoint_writer.write(gen, population, halloffame)

      if res.correct:
        logging.info('Solution found:\n%s\nreward = %s\n',
                     best_code, res.reward)
        break

    gen += 1

  best_code = ''.join(halloffame.get_max()[1])
  res = task_eval_fn(best_code)

  return GaResult(
      population=population, best_code=best_code, reward=res.reward,
      solution_found=res.correct, generations=gen,
      num_programs=gen * len(population),
      max_generations=ngen, max_num_programs=ngen * len(population))


GaResult = namedtuple(
    'GaResult',
    ['population', 'best_code', 'reward', 'generations', 'num_programs',
     'solution_found', 'max_generations', 'max_num_programs'])


def reward_conversion(reward):
  """Convert real value into positive value."""
  if reward <= 0:
    return 0.05
  return reward + 0.05


def roulette_selection(population, k):
  """Select `k` individuals with prob proportional to fitness.

  Each of the `k` selections is independent.

  Warning:
    The roulette selection by definition cannot be used for minimization
    or when the fitness can be smaller or equal to 0.

  Args:
    population: A list of Individual objects to select from.
    k: The number of individuals to select.

  Returns:
    A list of selected individuals.
  """
  fitnesses = np.asarray(
      [reward_conversion(ind.fitness.values[0])
       for ind in population])
  assert np.all(fitnesses > 0)

  sum_fits = fitnesses.sum()
  chosen = [None] * k
  for i in xrange(k):
    u = random.random() * sum_fits
    sum_ = 0
    for ind, fitness in zip(population, fitnesses):
      sum_ += fitness
      if sum_ > u:
        chosen[i] = Individual(ind)
        break
    if not chosen[i]:
      chosen[i] = Individual(population[-1])

  return chosen


def make_population(make_individual_fn, n):
  return [make_individual_fn() for _ in xrange(n)]


def best(population):
  best_ind = None
  for ind in population:
    if best_ind is None or best_ind.fitness.values < ind.fitness.values:
      best_ind = ind
  return best_ind


def topk(population, k):
  q = utils.MaxUniquePriorityQueue(k)
  for ind in population:
    q.push(ind.fitness.values, tuple(ind), ind)
  return [ind for _, ind in q.iter_in_order()]


class Fitness(object):

  def __init__(self):
    self.values = ()

  @property
  def valid(self):
    """Assess if a fitness is valid or not."""
    return bool(self.values)


class Individual(list):

  def __init__(self, *args):
    super(Individual, self).__init__(*args)
    self.fitness = Fitness()


def random_individual(genome_size):
  return lambda: Individual(np.random.choice(GENES, genome_size).tolist())

#This file: pg_agent.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Language model agent.

Agent outputs code in a sequence just like a language model. Can be trained
as a language model or using RL, or a combination of the two.
"""

from collections import namedtuple
from math import exp
from math import log
import time

from absl import logging
import numpy as np
from six.moves import xrange
import tensorflow as tf

from common import rollout as rollout_lib  # brain coder
from common import utils  # brain coder
from single_task import misc  # brain coder


# Experiments in the ICLR 2018 paper used reduce_sum instead of reduce_mean for
# some losses. We make all loses be batch_size independent, and multiply the
# changed losses by 64, which was the fixed batch_size when the experiments
# where run. The loss hyperparameters still match what is reported in the paper.
MAGIC_LOSS_MULTIPLIER = 64


def rshift_time(tensor_2d, fill=misc.BF_EOS_INT):
  """Right shifts a 2D tensor along the time dimension (axis-1)."""
  dim_0 = tf.shape(tensor_2d)[0]
  fill_tensor = tf.fill([dim_0, 1], fill)
  return tf.concat([fill_tensor, tensor_2d[:, :-1]], axis=1)


def join(a, b):
  # Concat a and b along 0-th dim.
  if a is None or len(a) == 0:  # pylint: disable=g-explicit-length-test
    return b
  if b is None or len(b) == 0:  # pylint: disable=g-explicit-length-test
    return a
  return np.concatenate((a, b))


def make_optimizer(kind, lr):
  if kind == 'sgd':
    return tf.train.GradientDescentOptimizer(lr)
  elif kind == 'adam':
    return tf.train.AdamOptimizer(lr)
  elif kind == 'rmsprop':
    return tf.train.RMSPropOptimizer(learning_rate=lr, decay=0.99)
  else:
    raise ValueError('Optimizer type "%s" not recognized.' % kind)


class LinearWrapper(tf.contrib.rnn.RNNCell):
  """RNNCell wrapper that adds a linear layer to the output."""

  def __init__(self, cell, output_size, dtype=tf.float32, suppress_index=None):
    self.cell = cell
    self._output_size = output_size
    self._dtype = dtype
    self._suppress_index = suppress_index
    self.smallest_float = -2.4e38

  def __call__(self, inputs, state, scope=None):
    with tf.variable_scope(type(self).__name__):
      outputs, state = self.cell(inputs, state, scope=scope)
      logits = tf.matmul(
          outputs,
          tf.get_variable('w_output',
                          [self.cell.output_size, self.output_size],
                          dtype=self._dtype))
      if self._suppress_index is not None:
        # Replace the target index with -inf, so that it never gets selected.
        batch_size = tf.shape(logits)[0]
        logits = tf.concat(
            [logits[:, :self._suppress_index],
             tf.fill([batch_size, 1], self.smallest_float),
             logits[:, self._suppress_index + 1:]],
            axis=1)

    return logits, state

  @property
  def output_size(self):
    return self._output_size

  @property
  def state_size(self):
    return self.cell.state_size

  def zero_state(self, batch_size, dtype):
    return self.cell.zero_state(batch_size, dtype)


UpdateStepResult = namedtuple(
    'UpdateStepResult',
    ['global_step', 'global_npe', 'summaries_list', 'gradients_dict'])


class AttrDict(dict):
  """Dict with attributes as keys.

  https://stackoverflow.com/a/14620633
  """

  def __init__(self, *args, **kwargs):
    super(AttrDict, self).__init__(*args, **kwargs)
    self.__dict__ = self


class LMAgent(object):
  """Language model agent."""
  action_space = misc.bf_num_tokens()
  observation_space = misc.bf_num_tokens()

  def __init__(self, global_config, task_id=0,
               logging_file=None,
               experience_replay_file=None,
               global_best_reward_fn=None,
               found_solution_op=None,
               assign_code_solution_fn=None,
               program_count=None,
               do_iw_summaries=False,
               stop_on_success=True,
               dtype=tf.float32,
               verbose_level=0,
               is_local=True):
    self.config = config = global_config.agent
    self.logging_file = logging_file
    self.experience_replay_file = experience_replay_file
    self.task_id = task_id
    self.verbose_level = verbose_level
    self.global_best_reward_fn = global_best_reward_fn
    self.found_solution_op = found_solution_op
    self.assign_code_solution_fn = assign_code_solution_fn
    self.parent_scope_name = tf.get_variable_scope().name
    self.dtype = dtype
    self.allow_eos_token = config.eos_token
    self.stop_on_success = stop_on_success
    self.pi_loss_hparam = config.pi_loss_hparam
    self.vf_loss_hparam = config.vf_loss_hparam
    self.is_local = is_local

    self.top_reward = 0.0
    self.embeddings_trainable = True

    self.no_op = tf.no_op()

    self.learning_rate = tf.constant(
        config.lr, dtype=dtype, name='learning_rate')
    self.initializer = tf.contrib.layers.variance_scaling_initializer(
        factor=config.param_init_factor,
        mode='FAN_AVG',
        uniform=True,
        dtype=dtype)  # TF's default initializer.
    tf.get_variable_scope().set_initializer(self.initializer)

    self.a2c = config.ema_baseline_decay == 0
    if not self.a2c:
      logging.info('Using exponential moving average REINFORCE baselines.')
      self.ema_baseline_decay = config.ema_baseline_decay
      self.ema_by_len = [0.0] * global_config.timestep_limit
    else:
      logging.info('Using advantage (a2c) with learned value function.')
      self.ema_baseline_decay = 0.0
      self.ema_by_len = None

    # Top-k
    if config.topk and config.topk_loss_hparam:
      self.topk_loss_hparam = config.topk_loss_hparam
      self.topk_batch_size = config.topk_batch_size
      if self.topk_batch_size <= 0:
        raise ValueError('topk_batch_size must be a positive integer. Got %s',
                         self.topk_batch_size)
      self.top_episodes = utils.MaxUniquePriorityQueue(config.topk)
      logging.info('Made max-priorty-queue with capacity %d',
                   self.top_episodes.capacity)
    else:
      self.top_episodes = None
      self.topk_loss_hparam = 0.0
      logging.info('No max-priorty-queue')

    # Experience replay.
    self.replay_temperature = config.replay_temperature
    self.num_replay_per_batch = int(global_config.batch_size * config.alpha)
    self.num_on_policy_per_batch = (
        global_config.batch_size - self.num_replay_per_batch)
    self.replay_alpha = (
        self.num_replay_per_batch / float(global_config.batch_size))
    logging.info('num_replay_per_batch: %d', self.num_replay_per_batch)
    logging.info('num_on_policy_per_batch: %d', self.num_on_policy_per_batch)
    logging.info('replay_alpha: %s', self.replay_alpha)
    if self.num_replay_per_batch > 0:
      # Train with off-policy episodes from replay buffer.
      start_time = time.time()
      self.experience_replay = utils.RouletteWheel(
          unique_mode=True, save_file=experience_replay_file)
      logging.info('Took %s sec to load replay buffer from disk.',
                   int(time.time() - start_time))
      logging.info('Replay buffer file location: "%s"',
                   self.experience_replay.save_file)
    else:
      # Only train on-policy.
      self.experience_replay = None

    if program_count is not None:
      self.program_count = program_count
      self.program_count_add_ph = tf.placeholder(
          tf.int64, [], 'program_count_add_ph')
      self.program_count_add_op = self.program_count.assign_add(
          self.program_count_add_ph)

    ################################
    # RL policy and value networks #
    ################################
    batch_size = global_config.batch_size
    logging.info('batch_size: %d', batch_size)

    self.policy_cell = LinearWrapper(
        tf.contrib.rnn.MultiRNNCell(
            [tf.contrib.rnn.BasicLSTMCell(cell_size)
             for cell_size in config.policy_lstm_sizes]),
        self.action_space,
        dtype=dtype,
        suppress_index=None if self.allow_eos_token else misc.BF_EOS_INT)
    self.value_cell = LinearWrapper(
        tf.contrib.rnn.MultiRNNCell(
            [tf.contrib.rnn.BasicLSTMCell(cell_size)
             for cell_size in config.value_lstm_sizes]),
        1,
        dtype=dtype)

    obs_embedding_scope = 'obs_embed'
    with tf.variable_scope(
        obs_embedding_scope,
        initializer=tf.random_uniform_initializer(minval=-1.0, maxval=1.0)):
      obs_embeddings = tf.get_variable(
          'embeddings',
          [self.observation_space, config.obs_embedding_size],
          dtype=dtype, trainable=self.embeddings_trainable)
      self.obs_embeddings = obs_embeddings

    ################################
    # RL policy and value networks #
    ################################

    initial_state = tf.fill([batch_size], misc.BF_EOS_INT)
    def loop_fn(loop_time, cell_output, cell_state, loop_state):
      """Function called by tf.nn.raw_rnn to instantiate body of the while_loop.

      See https://www.tensorflow.org/api_docs/python/tf/nn/raw_rnn for more
      information.

      When time is 0, and cell_output, cell_state, loop_state are all None,
      `loop_fn` will create the initial input, internal cell state, and loop
      state. When time > 0, `loop_fn` will operate on previous cell output,
      state, and loop state.

      Args:
        loop_time: A scalar tensor holding the current timestep (zero based
            counting).
        cell_output: Output of the raw_rnn cell at the current timestep.
        cell_state: Cell internal state at the current timestep.
        loop_state: Additional loop state. These tensors were returned by the
            previous call to `loop_fn`.

      Returns:
        elements_finished: Bool tensor of shape [batch_size] which marks each
            sequence in the batch as being finished or not finished.
        next_input: A tensor containing input to be fed into the cell at the
            next timestep.
        next_cell_state: Cell internal state to be fed into the cell at the
            next timestep.
        emit_output: Tensor to be added to the TensorArray returned by raw_rnn
            as output from the while_loop.
        next_loop_state: Additional loop state. These tensors will be fed back
            into the next call to `loop_fn` as `loop_state`.
      """
      if cell_output is None:  # 0th time step.
        next_cell_state = self.policy_cell.zero_state(batch_size, dtype)
        elements_finished = tf.zeros([batch_size], tf.bool)
        output_lengths = tf.ones([batch_size], dtype=tf.int32)
        next_input = tf.gather(obs_embeddings, initial_state)
        emit_output = None
        next_loop_state = (
            tf.TensorArray(dtype=tf.int32, size=0, dynamic_size=True),
            output_lengths,
            elements_finished
        )
      else:
        scaled_logits = cell_output * config.softmax_tr  # Scale temperature.
        prev_chosen, prev_output_lengths, prev_elements_finished = loop_state
        next_cell_state = cell_state
        chosen_outputs = tf.to_int32(tf.where(
            tf.logical_not(prev_elements_finished),
            tf.multinomial(logits=scaled_logits, num_samples=1)[:, 0],
            tf.zeros([batch_size], dtype=tf.int64)))
        elements_finished = tf.logical_or(
            tf.equal(chosen_outputs, misc.BF_EOS_INT),
            loop_time >= global_config.timestep_limit)
        output_lengths = tf.where(
            elements_finished,
            prev_output_lengths,
            # length includes EOS token. empty seq has len 1.
            tf.tile(tf.expand_dims(loop_time + 1, 0), [batch_size])
        )
        next_input = tf.gather(obs_embeddings, chosen_outputs)
        emit_output = scaled_logits
        next_loop_state = (prev_chosen.write(loop_time - 1, chosen_outputs),
                           output_lengths,
                           tf.logical_or(prev_elements_finished,
                                         elements_finished))
      return (elements_finished, next_input, next_cell_state, emit_output,
              next_loop_state)

    with tf.variable_scope('policy'):
      (decoder_outputs_ta,
       _,  # decoder_state
       (sampled_output_ta, output_lengths, _)) = tf.nn.raw_rnn(
           cell=self.policy_cell,
           loop_fn=loop_fn)
    policy_logits = tf.transpose(decoder_outputs_ta.stack(), (1, 0, 2),
                                 name='policy_logits')
    sampled_tokens = tf.transpose(sampled_output_ta.stack(), (1, 0),
                                  name='sampled_tokens')
    # Add SOS to beginning of the sequence.
    rshift_sampled_tokens = rshift_time(sampled_tokens, fill=misc.BF_EOS_INT)

    # Initial state is 0, 2nd state is first token.
    # Note: If value of last state is computed, this will be used as bootstrap.
    if self.a2c:
      with tf.variable_scope('value'):
        value_output, _ = tf.nn.dynamic_rnn(
            self.value_cell,
            tf.gather(obs_embeddings, rshift_sampled_tokens),
            sequence_length=output_lengths,
            dtype=dtype)
      value = tf.squeeze(value_output, axis=[2])
    else:
      value = tf.zeros([], dtype=dtype)

    # for sampling actions from the agent, and which told tensors for doing
    # gradient updates on the agent.
    self.sampled_batch = AttrDict(
        logits=policy_logits,
        value=value,
        tokens=sampled_tokens,
        episode_lengths=output_lengths,
        probs=tf.nn.softmax(policy_logits),
        log_probs=tf.nn.log_softmax(policy_logits))

    # adjusted_lengths can be less than the full length of each episode.
    # Use this to train on only part of an episode (starting from t=0).
    self.adjusted_lengths = tf.placeholder(
        tf.int32, [None], name='adjusted_lengths')
    self.policy_multipliers = tf.placeholder(
        dtype,
        [None, None],
        name='policy_multipliers')
    # Empirical value, i.e. discounted sum of observed future rewards from each
    # time step in the episode.
    self.empirical_values = tf.placeholder(
        dtype,
        [None, None],
        name='empirical_values')

    # Off-policy training. Just add supervised loss to the RL loss.
    self.off_policy_targets = tf.placeholder(
        tf.int32,
        [None, None],
        name='off_policy_targets')
    self.off_policy_target_lengths = tf.placeholder(
        tf.int32, [None], name='off_policy_target_lengths')

    self.actions = tf.placeholder(tf.int32, [None, None], name='actions')
    # Add SOS to beginning of the sequence.
    inputs = rshift_time(self.actions, fill=misc.BF_EOS_INT)
    with tf.variable_scope('policy', reuse=True):
      logits, _ = tf.nn.dynamic_rnn(
          self.policy_cell, tf.gather(obs_embeddings, inputs),
          sequence_length=self.adjusted_lengths,
          dtype=dtype)

    if self.a2c:
      with tf.variable_scope('value', reuse=True):
        value_output, _ = tf.nn.dynamic_rnn(
            self.value_cell,
            tf.gather(obs_embeddings, inputs),
            sequence_length=self.adjusted_lengths,
            dtype=dtype)
      value2 = tf.squeeze(value_output, axis=[2])
    else:
      value2 = tf.zeros([], dtype=dtype)

    self.given_batch = AttrDict(
        logits=logits,
        value=value2,
        tokens=sampled_tokens,
        episode_lengths=self.adjusted_lengths,
        probs=tf.nn.softmax(logits),
        log_probs=tf.nn.log_softmax(logits))

    # Episode masks.
    max_episode_length = tf.shape(self.actions)[1]
    # range_row shape: [1, max_episode_length]
    range_row = tf.expand_dims(tf.range(max_episode_length), 0)
    episode_masks = tf.cast(
        tf.less(range_row, tf.expand_dims(self.given_batch.episode_lengths, 1)),
        dtype=dtype)
    episode_masks_3d = tf.expand_dims(episode_masks, 2)

    # Length adjusted episodes.
    self.a_probs = a_probs = self.given_batch.probs * episode_masks_3d
    self.a_log_probs = a_log_probs = (
        self.given_batch.log_probs * episode_masks_3d)
    self.a_value = a_value = self.given_batch.value * episode_masks
    self.a_policy_multipliers = a_policy_multipliers = (
        self.policy_multipliers * episode_masks)
    if self.a2c:
      self.a_empirical_values = a_empirical_values = (
          self.empirical_values * episode_masks)

    # pi_loss is scalar
    acs_onehot = tf.one_hot(self.actions, self.action_space, dtype=dtype)
    self.acs_onehot = acs_onehot
    chosen_masked_log_probs = acs_onehot * a_log_probs
    pi_target = tf.expand_dims(a_policy_multipliers, -1)
    pi_loss_per_step = chosen_masked_log_probs * pi_target  # Maximize.
    self.pi_loss = pi_loss = (
        -tf.reduce_mean(tf.reduce_sum(pi_loss_per_step, axis=[1, 2]), axis=0)
        * MAGIC_LOSS_MULTIPLIER)  # Minimize.
    assert len(self.pi_loss.shape) == 0  # pylint: disable=g-explicit-length-test

    # shape: [batch_size, time]
    self.chosen_log_probs = tf.reduce_sum(chosen_masked_log_probs, axis=2)
    self.chosen_probs = tf.reduce_sum(acs_onehot * a_probs, axis=2)

    # loss of value function
    if self.a2c:
      vf_loss_per_step = tf.square(a_value - a_empirical_values)
      self.vf_loss = vf_loss = (
          tf.reduce_mean(tf.reduce_sum(vf_loss_per_step, axis=1), axis=0)
          * MAGIC_LOSS_MULTIPLIER)  # Minimize.
      assert len(self.vf_loss.shape) == 0  # pylint: disable=g-explicit-length-test
    else:
      self.vf_loss = vf_loss = 0.0

    # Maximize entropy regularizer
    self.entropy = entropy = (
        -tf.reduce_mean(
            tf.reduce_sum(a_probs * a_log_probs, axis=[1, 2]), axis=0)
        * MAGIC_LOSS_MULTIPLIER)  # Maximize
    self.negentropy = -entropy  # Minimize negentropy.
    assert len(self.negentropy.shape) == 0  # pylint: disable=g-explicit-length-test

    # off-policy loss
    self.offp_switch = tf.placeholder(dtype, [], name='offp_switch')
    if self.top_episodes is not None:
      # Add SOS to beginning of the sequence.
      offp_inputs = tf.gather(obs_embeddings,
                              rshift_time(self.off_policy_targets,
                                          fill=misc.BF_EOS_INT))
      with tf.variable_scope('policy', reuse=True):
        offp_logits, _ = tf.nn.dynamic_rnn(
            self.policy_cell, offp_inputs, self.off_policy_target_lengths,
            dtype=dtype)  # shape: [batch_size, time, action_space]
      topk_loss_per_step = tf.nn.sparse_softmax_cross_entropy_with_logits(
          labels=self.off_policy_targets,
          logits=offp_logits,
          name='topk_loss_per_logit')
      # Take mean over batch dimension so that the loss multiplier strength is
      # independent of batch size. Sum over time dimension.
      topk_loss = tf.reduce_mean(
          tf.reduce_sum(topk_loss_per_step, axis=1), axis=0)
      assert len(topk_loss.shape) == 0  # pylint: disable=g-explicit-length-test
      self.topk_loss = topk_loss * self.offp_switch
      logging.info('Including off policy loss.')
    else:
      self.topk_loss = topk_loss = 0.0

    self.entropy_hparam = tf.constant(
        config.entropy_beta, dtype=dtype, name='entropy_beta')

    self.pi_loss_term = pi_loss * self.pi_loss_hparam
    self.vf_loss_term = vf_loss * self.vf_loss_hparam
    self.entropy_loss_term = self.negentropy * self.entropy_hparam
    self.topk_loss_term = self.topk_loss_hparam * topk_loss
    self.loss = (
        self.pi_loss_term
        + self.vf_loss_term
        + self.entropy_loss_term
        + self.topk_loss_term)

    params = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,
                               tf.get_variable_scope().name)
    self.trainable_variables = params
    self.sync_variables = self.trainable_variables
    non_embedding_params = [p for p in params
                            if obs_embedding_scope not in p.name]
    self.non_embedding_params = non_embedding_params
    self.params = params

    if config.regularizer:
      logging.info('Adding L2 regularizer with scale %.2f.',
                   config.regularizer)
      self.regularizer = config.regularizer * sum(
          tf.nn.l2_loss(w) for w in non_embedding_params)
      self.loss += self.regularizer
    else:
      logging.info('Skipping regularizer.')
      self.regularizer = 0.0

    # Only build gradients graph for local model.
    if self.is_local:
      unclipped_grads = tf.gradients(self.loss, params)
      self.dense_unclipped_grads = [
          tf.convert_to_tensor(g) for g in unclipped_grads]
      self.grads, self.global_grad_norm = tf.clip_by_global_norm(
          unclipped_grads, config.grad_clip_threshold)
      self.gradients_dict = dict(zip(params, self.grads))
      self.optimizer = make_optimizer(config.optimizer, self.learning_rate)
      self.all_variables = tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES,
                                             tf.get_variable_scope().name)

    self.do_iw_summaries = do_iw_summaries
    if self.do_iw_summaries:
      b = None
      self.log_iw_replay_ph = tf.placeholder(tf.float32, [b],
                                             'log_iw_replay_ph')
      self.log_iw_policy_ph = tf.placeholder(tf.float32, [b],
                                             'log_iw_policy_ph')
      self.log_prob_replay_ph = tf.placeholder(tf.float32, [b],
                                               'log_prob_replay_ph')
      self.log_prob_policy_ph = tf.placeholder(tf.float32, [b],
                                               'log_prob_policy_ph')
      self.log_norm_replay_weights_ph = tf.placeholder(
          tf.float32, [b], 'log_norm_replay_weights_ph')
      self.iw_summary_op = tf.summary.merge([
          tf.summary.histogram('is/log_iw_replay', self.log_iw_replay_ph),
          tf.summary.histogram('is/log_iw_policy', self.log_iw_policy_ph),
          tf.summary.histogram('is/log_prob_replay', self.log_prob_replay_ph),
          tf.summary.histogram('is/log_prob_policy', self.log_prob_policy_ph),
          tf.summary.histogram(
              'is/log_norm_replay_weights', self.log_norm_replay_weights_ph),
      ])

  def make_summary_ops(self):
    """Construct summary ops for the model."""
    # size = number of timesteps across entire batch. Number normalized by size
    # will not be affected by the amount of padding at the ends of sequences
    # in the batch.
    size = tf.cast(
        tf.reduce_sum(self.given_batch.episode_lengths), dtype=self.dtype)
    offp_size = tf.cast(tf.reduce_sum(self.off_policy_target_lengths),
                        dtype=self.dtype)
    scope_prefix = self.parent_scope_name

    def _remove_prefix(prefix, name):
      assert name.startswith(prefix)
      return name[len(prefix):]

    # RL summaries.
    self.rl_summary_op = tf.summary.merge(
        [tf.summary.scalar('model/policy_loss', self.pi_loss / size),
         tf.summary.scalar('model/value_loss', self.vf_loss / size),
         tf.summary.scalar('model/topk_loss', self.topk_loss / offp_size),
         tf.summary.scalar('model/entropy', self.entropy / size),
         tf.summary.scalar('model/loss', self.loss / size),
         tf.summary.scalar('model/grad_norm',
                           tf.global_norm(self.grads)),
         tf.summary.scalar('model/unclipped_grad_norm', self.global_grad_norm),
         tf.summary.scalar('model/non_embedding_var_norm',
                           tf.global_norm(self.non_embedding_params)),
         tf.summary.scalar('hparams/entropy_beta', self.entropy_hparam),
         tf.summary.scalar('hparams/topk_loss_hparam', self.topk_loss_hparam),
         tf.summary.scalar('hparams/learning_rate', self.learning_rate),
         tf.summary.scalar('model/trainable_var_norm',
                           tf.global_norm(self.trainable_variables)),
         tf.summary.scalar('loss/loss', self.loss),
         tf.summary.scalar('loss/entropy', self.entropy_loss_term),
         tf.summary.scalar('loss/vf', self.vf_loss_term),
         tf.summary.scalar('loss/policy', self.pi_loss_term),
         tf.summary.scalar('loss/offp', self.topk_loss_term)] +
        [tf.summary.scalar(
            'param_norms/' + _remove_prefix(scope_prefix + '/', p.name),
            tf.norm(p))
         for p in self.params] +
        [tf.summary.scalar(
            'grad_norms/' + _remove_prefix(scope_prefix + '/', p.name),
            tf.norm(g))
         for p, g in zip(self.params, self.grads)] +
        [tf.summary.scalar(
            'unclipped_grad_norms/' + _remove_prefix(scope_prefix + '/',
                                                     p.name),
            tf.norm(g))
         for p, g in zip(self.params, self.dense_unclipped_grads)])

    self.text_summary_placeholder = tf.placeholder(tf.string, shape=[])
    self.rl_text_summary_op = tf.summary.text('rl',
                                              self.text_summary_placeholder)

  def _rl_text_summary(self, session, step, npe, tot_r, num_steps,
                       input_case, code_output, code, reason):
    """Logs summary about a single episode and creates a text_summary for TB.

    Args:
      session: tf.Session instance.
      step: Global training step.
      npe: Number of programs executed so far.
      tot_r: Total reward.
      num_steps: Number of timesteps in the episode (i.e. code length).
      input_case: Inputs for test cases.
      code_output: Outputs produced by running the code on the inputs.
      code: String representation of the code.
      reason: Reason for the reward assigned by the task.

    Returns:
      Serialized text summary data for tensorboard.
    """
    if not input_case:
      input_case = ' '
    if not code_output:
      code_output = ' '
    if not code:
      code = ' '
    text = (
        'Tot R: **%.2f**;  Len: **%d**;  Reason: **%s**\n\n'
        'Input: **`%s`**; Output: **`%s`**\n\nCode: **`%s`**'
        % (tot_r, num_steps, reason, input_case, code_output, code))
    text_summary = session.run(self.rl_text_summary_op,
                               {self.text_summary_placeholder: text})
    logging.info(
        'Step %d.\t NPE: %d\t Reason: %s.\t Tot R: %.2f.\t Length: %d. '
        '\tInput: %s \tOutput: %s \tProgram: %s',
        step, npe, reason, tot_r, num_steps, input_case,
        code_output, code)
    return text_summary

  def _rl_reward_summary(self, total_rewards):
    """Create summary ops that report on episode rewards.

    Creates summaries for average, median, max, and min rewards in the batch.

    Args:
      total_rewards: Tensor of shape [batch_size] containing the total reward
          from each episode in the batch.

    Returns:
      tf.Summary op.
    """
    tr = np.asarray(total_rewards)
    reward_summary = tf.Summary(value=[
        tf.Summary.Value(
            tag='reward/avg',
            simple_value=np.mean(tr)),
        tf.Summary.Value(
            tag='reward/med',
            simple_value=np.median(tr)),
        tf.Summary.Value(
            tag='reward/max',
            simple_value=np.max(tr)),
        tf.Summary.Value(
            tag='reward/min',
            simple_value=np.min(tr))])
    return reward_summary

  def _iw_summary(self, session, replay_iw, replay_log_probs,
                  norm_replay_weights, on_policy_iw,
                  on_policy_log_probs):
    """Compute summaries for importance weights at a given batch.

    Args:
      session: tf.Session instance.
      replay_iw: Importance weights for episodes from replay buffer.
      replay_log_probs: Total log probabilities of the replay episodes under the
          current policy.
      norm_replay_weights: Normalized replay weights, i.e. values in `replay_iw`
          divided by the total weight in the entire replay buffer. Note, this is
          also the probability of selecting each episode from the replay buffer
          (in a roulette wheel replay buffer).
      on_policy_iw: Importance weights for episodes sampled from the current
          policy.
      on_policy_log_probs: Total log probabilities of the on-policy episodes
          under the current policy.

    Returns:
      Serialized TF summaries. Use a summary writer to write these summaries to
      disk.
    """
    return session.run(
        self.iw_summary_op,
        {self.log_iw_replay_ph: np.log(replay_iw),
         self.log_iw_policy_ph: np.log(on_policy_iw),
         self.log_norm_replay_weights_ph: np.log(norm_replay_weights),
         self.log_prob_replay_ph: replay_log_probs,
         self.log_prob_policy_ph: on_policy_log_probs})

  def _compute_iw(self, policy_log_probs, replay_weights):
    """Compute importance weights for a batch of episodes.

    Arguments are iterables of length batch_size.

    Args:
      policy_log_probs: Log probability of each episode under the current
          policy.
      replay_weights: Weight of each episode in the replay buffer. 0 for
          episodes not sampled from the replay buffer (i.e. sampled from the
          policy).

    Returns:
      Numpy array of shape [batch_size] containing the importance weight for
      each episode in the batch.
    """
    log_total_replay_weight = log(self.experience_replay.total_weight)

    # importance weight
    # = 1 / [(1 - a) + a * exp(log(replay_weight / total_weight / p))]
    # = 1 / ((1-a) + a*q/p)
    a = float(self.replay_alpha)
    a_com = 1.0 - a  # compliment of a
    importance_weights = np.asarray(
        [1.0 / (a_com
                + a * exp((log(replay_weight) - log_total_replay_weight)
                          - log_p))
         if replay_weight > 0 else 1.0 / a_com
         for log_p, replay_weight
         in zip(policy_log_probs, replay_weights)])
    return importance_weights

  def update_step(self, session, rl_batch, train_op, global_step_op,
                  return_gradients=False):
    """Perform gradient update on the model.

    Args:
      session: tf.Session instance.
      rl_batch: RLBatch instance from data.py. Use DataManager to create a
          RLBatch for each call to update_step. RLBatch contains a batch of
          tasks.
      train_op: A TF op which will perform the gradient update. LMAgent does not
          own its training op, so that trainers can do distributed training
          and construct a specialized training op.
      global_step_op: A TF op which will return the current global step when
          run (should not increment it).
      return_gradients: If True, the gradients will be saved and returned from
          this method call. This is useful for testing.

    Returns:
      Results from the update step in a UpdateStepResult namedtuple, including
      global step, global NPE, serialized summaries, and optionally gradients.
    """
    assert self.is_local

    # Do update for REINFORCE or REINFORCE + replay buffer.
    if self.experience_replay is None:
      # Train with on-policy REINFORCE.

      # Sample new programs from the policy.
      num_programs_from_policy = rl_batch.batch_size
      (batch_actions,
       batch_values,
       episode_lengths) = session.run(
           [self.sampled_batch.tokens, self.sampled_batch.value,
            self.sampled_batch.episode_lengths])
      if episode_lengths.size == 0:
        # This should not happen.
        logging.warn(
            'Shapes:\n'
            'batch_actions.shape: %s\n'
            'batch_values.shape: %s\n'
            'episode_lengths.shape: %s\n',
            batch_actions.shape, batch_values.shape, episode_lengths.shape)

      # Compute rewards.
      code_scores = compute_rewards(
          rl_batch, batch_actions, episode_lengths)
      code_strings = code_scores.code_strings
      batch_tot_r = code_scores.total_rewards
      test_cases = code_scores.test_cases
      code_outputs = code_scores.code_outputs
      reasons = code_scores.reasons

      # Process on-policy samples.
      batch_targets, batch_returns = process_episodes(
          code_scores.batch_rewards, episode_lengths, a2c=self.a2c,
          baselines=self.ema_by_len,
          batch_values=batch_values)
      batch_policy_multipliers = batch_targets
      batch_emp_values = batch_returns if self.a2c else [[]]
      adjusted_lengths = episode_lengths

      if self.top_episodes:
        assert len(self.top_episodes) > 0  # pylint: disable=g-explicit-length-test
        off_policy_targets = [
            item for item, _
            in self.top_episodes.random_sample(self.topk_batch_size)]
        off_policy_target_lengths = [len(t) for t in off_policy_targets]
        off_policy_targets = utils.stack_pad(off_policy_targets, pad_axes=0,
                                             dtype=np.int32)
        offp_switch = 1
      else:
        off_policy_targets = [[0]]
        off_policy_target_lengths = [1]
        offp_switch = 0

      fetches = {
          'global_step': global_step_op,
          'program_count': self.program_count,
          'summaries': self.rl_summary_op,
          'train_op': train_op,
          'gradients': self.gradients_dict if return_gradients else self.no_op}
      fetched = session.run(
          fetches,
          {self.actions: batch_actions,
           self.empirical_values: batch_emp_values,
           self.policy_multipliers: batch_policy_multipliers,
           self.adjusted_lengths: adjusted_lengths,
           self.off_policy_targets: off_policy_targets,
           self.off_policy_target_lengths: off_policy_target_lengths,
           self.offp_switch: offp_switch})

      combined_adjusted_lengths = adjusted_lengths
      combined_returns = batch_returns
    else:
      # Train with REINFORCE + off-policy replay buffer by using importance
      # sampling.

      # Sample new programs from the policy.
      # Note: batch size is constant. A full batch will be sampled, but not all
      # programs will be executed and added to the replay buffer. Those which
      # are not executed will be discarded and not counted.
      batch_actions, batch_values, episode_lengths, log_probs = session.run(
          [self.sampled_batch.tokens, self.sampled_batch.value,
           self.sampled_batch.episode_lengths, self.sampled_batch.log_probs])
      if episode_lengths.size == 0:
        # This should not happen.
        logging.warn(
            'Shapes:\n'
            'batch_actions.shape: %s\n'
            'batch_values.shape: %s\n'
            'episode_lengths.shape: %s\n',
            batch_actions.shape, batch_values.shape, episode_lengths.shape)

      # Sample from experince replay buffer
      empty_replay_buffer = (
          self.experience_replay.is_empty()
          if self.experience_replay is not None else True)
      num_programs_from_replay_buff = (
          self.num_replay_per_batch if not empty_replay_buffer else 0)
      num_programs_from_policy = (
          rl_batch.batch_size - num_programs_from_replay_buff)
      if (not empty_replay_buffer) and num_programs_from_replay_buff:
        result = self.experience_replay.sample_many(
            num_programs_from_replay_buff)
        experience_samples, replay_weights = zip(*result)
        (replay_actions,
         replay_rewards,
         _,  # log probs
         replay_adjusted_lengths) = zip(*experience_samples)

        replay_batch_actions = utils.stack_pad(replay_actions, pad_axes=0,
                                               dtype=np.int32)

        # compute log probs for replay samples under current policy
        all_replay_log_probs, = session.run(
            [self.given_batch.log_probs],
            {self.actions: replay_batch_actions,
             self.adjusted_lengths: replay_adjusted_lengths})
        replay_log_probs = [
            np.choose(replay_actions[i], all_replay_log_probs[i, :l].T).sum()
            for i, l in enumerate(replay_adjusted_lengths)]
      else:
        # Replay buffer is empty. Do not sample from it.
        replay_actions = None
        replay_policy_multipliers = None
        replay_adjusted_lengths = None
        replay_log_probs = None
        replay_weights = None
        replay_returns = None
        on_policy_weights = [0] * num_programs_from_replay_buff

      assert not self.a2c  # TODO(danabo): Support A2C with importance sampling.

      # Compute rewards.
      code_scores = compute_rewards(
          rl_batch, batch_actions, episode_lengths,
          batch_size=num_programs_from_policy)
      code_strings = code_scores.code_strings
      batch_tot_r = code_scores.total_rewards
      test_cases = code_scores.test_cases
      code_outputs = code_scores.code_outputs
      reasons = code_scores.reasons

      # Process on-policy samples.
      p = num_programs_from_policy
      batch_targets, batch_returns = process_episodes(
          code_scores.batch_rewards, episode_lengths[:p], a2c=False,
          baselines=self.ema_by_len)
      batch_policy_multipliers = batch_targets
      batch_emp_values = [[]]
      on_policy_returns = batch_returns

      # Process off-policy samples.
      if (not empty_replay_buffer) and num_programs_from_replay_buff:
        offp_batch_rewards = [
            [0.0] * (l - 1) + [r]
            for l, r in zip(replay_adjusted_lengths, replay_rewards)]
        assert len(offp_batch_rewards) == num_programs_from_replay_buff
        assert len(replay_adjusted_lengths) == num_programs_from_replay_buff
        replay_batch_targets, replay_returns = process_episodes(
            offp_batch_rewards, replay_adjusted_lengths, a2c=False,
            baselines=self.ema_by_len)
        # Convert 2D array back into ragged 2D list.
        replay_policy_multipliers = [
            replay_batch_targets[i, :l]
            for i, l
            in enumerate(
                replay_adjusted_lengths[:num_programs_from_replay_buff])]

      adjusted_lengths = episode_lengths[:num_programs_from_policy]

      if self.top_episodes:
        assert len(self.top_episodes) > 0  # pylint: disable=g-explicit-length-test
        off_policy_targets = [
            item for item, _
            in self.top_episodes.random_sample(self.topk_batch_size)]
        off_policy_target_lengths = [len(t) for t in off_policy_targets]
        off_policy_targets = utils.stack_pad(off_policy_targets, pad_axes=0,
                                             dtype=np.int32)
        offp_switch = 1
      else:
        off_policy_targets = [[0]]
        off_policy_target_lengths = [1]
        offp_switch = 0

      # On-policy episodes.
      if num_programs_from_policy:
        separate_actions = [
            batch_actions[i, :l]
            for i, l in enumerate(adjusted_lengths)]
        chosen_log_probs = [
            np.choose(separate_actions[i], log_probs[i, :l].T)
            for i, l in enumerate(adjusted_lengths)]
        new_experiences = [
            (separate_actions[i],
             batch_tot_r[i],
             chosen_log_probs[i].sum(), l)
            for i, l in enumerate(adjusted_lengths)]
        on_policy_policy_multipliers = [
            batch_policy_multipliers[i, :l]
            for i, l in enumerate(adjusted_lengths)]
        (on_policy_actions,
         _,  # rewards
         on_policy_log_probs,
         on_policy_adjusted_lengths) = zip(*new_experiences)
      else:
        new_experiences = []
        on_policy_policy_multipliers = []
        on_policy_actions = []
        on_policy_log_probs = []
        on_policy_adjusted_lengths = []

      if (not empty_replay_buffer) and num_programs_from_replay_buff:
        # Look for new experiences in replay buffer. Assign weight if an episode
        # is in the buffer.
        on_policy_weights = [0] * num_programs_from_policy
        for i, cs in enumerate(code_strings):
          if self.experience_replay.has_key(cs):
            on_policy_weights[i] = self.experience_replay.get_weight(cs)

      # Randomly select on-policy or off policy episodes to train on.
      combined_actions = join(replay_actions, on_policy_actions)
      combined_policy_multipliers = join(
          replay_policy_multipliers, on_policy_policy_multipliers)
      combined_adjusted_lengths = join(
          replay_adjusted_lengths, on_policy_adjusted_lengths)
      combined_returns = join(replay_returns, on_policy_returns)
      combined_actions = utils.stack_pad(combined_actions, pad_axes=0)
      combined_policy_multipliers = utils.stack_pad(combined_policy_multipliers,
                                                    pad_axes=0)
      # P
      combined_on_policy_log_probs = join(replay_log_probs, on_policy_log_probs)
      # Q
      # Assume weight is zero for all sequences sampled from the policy.
      combined_q_weights = join(replay_weights, on_policy_weights)

      # Importance adjustment. Naive formulation:
      # E_{x~p}[f(x)] ~= 1/N sum_{x~p}(f(x)) ~= 1/N sum_{x~q}(f(x) * p(x)/q(x)).
      # p(x) is the policy, and q(x) is the off-policy distribution, i.e. replay
      # buffer distribution. Importance weight w(x) = p(x) / q(x).

      # Instead of sampling from the replay buffer only, we sample from a
      # mixture distribution of the policy and replay buffer.
      # We are sampling from the mixture a*q(x) + (1-a)*p(x), where 0 <= a <= 1.
      # Thus the importance weight w(x) = p(x) / (a*q(x) + (1-a)*p(x))
      # = 1 / ((1-a) + a*q(x)/p(x)) where q(x) is 0 for x sampled from the
      #                             policy.
      # Note: a = self.replay_alpha
      if empty_replay_buffer:
        # The replay buffer is empty.
        # Do no gradient update this step. The replay buffer will have stuff in
        # it next time.
        combined_policy_multipliers *= 0
      elif not num_programs_from_replay_buff:
        combined_policy_multipliers = np.ones([len(combined_actions), 1],
                                              dtype=np.float32)
      else:
        # If a < 1 compute importance weights
        # importance weight
        # = 1 / [(1 - a) + a * exp(log(replay_weight / total_weight / p))]
        # = 1 / ((1-a) + a*q/p)
        importance_weights = self._compute_iw(combined_on_policy_log_probs,
                                              combined_q_weights)
        if self.config.iw_normalize:
          importance_weights *= (
              float(rl_batch.batch_size) / importance_weights.sum())
        combined_policy_multipliers *= importance_weights.reshape(-1, 1)

      # Train on replay batch, top-k MLE.
      assert self.program_count is not None
      fetches = {
          'global_step': global_step_op,
          'program_count': self.program_count,
          'summaries': self.rl_summary_op,
          'train_op': train_op,
          'gradients': self.gradients_dict if return_gradients else self.no_op}
      fetched = session.run(
          fetches,
          {self.actions: combined_actions,
           self.empirical_values: [[]],  # replay_emp_values,
           self.policy_multipliers: combined_policy_multipliers,
           self.adjusted_lengths: combined_adjusted_lengths,
           self.off_policy_targets: off_policy_targets,
           self.off_policy_target_lengths: off_policy_target_lengths,
           self.offp_switch: offp_switch})

      # Add to experience replay buffer.
      self.experience_replay.add_many(
          objs=new_experiences,
          weights=[exp(r / self.replay_temperature) for r in batch_tot_r],
          keys=code_strings)

    # Update program count.
    session.run(
        [self.program_count_add_op],
        {self.program_count_add_ph: num_programs_from_policy})

    # Update EMA baselines on the mini-batch which we just did traning on.
    if not self.a2c:
      for i in xrange(rl_batch.batch_size):
        episode_length = combined_adjusted_lengths[i]
        empirical_returns = combined_returns[i, :episode_length]
        for j in xrange(episode_length):
          # Update ema_baselines in place.
          self.ema_by_len[j] = (
              self.ema_baseline_decay * self.ema_by_len[j]
              + (1 - self.ema_baseline_decay) * empirical_returns[j])

    global_step = fetched['global_step']
    global_npe = fetched['program_count']
    core_summaries = fetched['summaries']
    summaries_list = [core_summaries]

    if num_programs_from_policy:
      s_i = 0
      text_summary = self._rl_text_summary(
          session,
          global_step,
          global_npe,
          batch_tot_r[s_i],
          episode_lengths[s_i], test_cases[s_i],
          code_outputs[s_i], code_strings[s_i], reasons[s_i])
      reward_summary = self._rl_reward_summary(batch_tot_r)

      is_best = False
      if self.global_best_reward_fn:
        # Save best reward.
        best_reward = np.max(batch_tot_r)
        is_best = self.global_best_reward_fn(session, best_reward)

      if self.found_solution_op is not None and 'correct' in reasons:
        session.run(self.found_solution_op)

        # Save program to disk for record keeping.
        if self.stop_on_success:
          solutions = [
              {'code': code_strings[i], 'reward': batch_tot_r[i],
               'npe': global_npe}
              for i in xrange(len(reasons)) if reasons[i] == 'correct']
        elif is_best:
          solutions = [
              {'code': code_strings[np.argmax(batch_tot_r)],
               'reward': np.max(batch_tot_r),
               'npe': global_npe}]
        else:
          solutions = []
        if solutions:
          if self.assign_code_solution_fn:
            self.assign_code_solution_fn(session, solutions[0]['code'])
          with tf.gfile.FastGFile(self.logging_file, 'a') as writer:
            for solution_dict in solutions:
              writer.write(str(solution_dict) + '\n')

      max_i = np.argmax(batch_tot_r)
      max_tot_r = batch_tot_r[max_i]
      if max_tot_r >= self.top_reward:
        if max_tot_r >= self.top_reward:
          self.top_reward = max_tot_r
        logging.info('Top code: r=%.2f, \t%s', max_tot_r, code_strings[max_i])
      if self.top_episodes is not None:
        self.top_episodes.push(
            max_tot_r, tuple(batch_actions[max_i, :episode_lengths[max_i]]))

      summaries_list += [text_summary, reward_summary]

      if self.do_iw_summaries and not empty_replay_buffer:
        # prob of replay samples under replay buffer sampling.
        norm_replay_weights = [
            w / self.experience_replay.total_weight
            for w in replay_weights]
        replay_iw = self._compute_iw(replay_log_probs, replay_weights)
        on_policy_iw = self._compute_iw(on_policy_log_probs, on_policy_weights)
        summaries_list.append(
            self._iw_summary(
                session, replay_iw, replay_log_probs, norm_replay_weights,
                on_policy_iw, on_policy_log_probs))

    return UpdateStepResult(
        global_step=global_step,
        global_npe=global_npe,
        summaries_list=summaries_list,
        gradients_dict=fetched['gradients'])


def io_to_text(io_case, io_type):
  if isinstance(io_case, misc.IOTuple):
    # If there are many strings, join them with ','.
    return ','.join([io_to_text(e, io_type) for e in io_case])
  if io_type == misc.IOType.string:
    # There is one string. Return it.
    return misc.tokens_to_text(io_case)
  if (io_type == misc.IOType.integer
      or io_type == misc.IOType.boolean):
    if len(io_case) == 1:
      return str(io_case[0])
    return str(io_case)


CodeScoreInfo = namedtuple(
    'CodeScoreInfo',
    ['code_strings', 'batch_rewards', 'total_rewards', 'test_cases',
     'code_outputs', 'reasons'])


def compute_rewards(rl_batch, batch_actions, episode_lengths, batch_size=None):
  """Compute rewards for each episode in the batch.

  Args:
    rl_batch: A data.RLBatch instance. This holds information about the task
        each episode is solving, and a reward function for each episode.
    batch_actions: Contains batch of episodes. Each sequence of actions will be
        converted into a BF program and then scored. A numpy array of shape
        [batch_size, max_sequence_length].
    episode_lengths: The sequence length of each episode in the batch. Iterable
        of length batch_size.
    batch_size: (optional) number of programs to score. Use this to limit the
        number of programs executed from this batch. For example, when doing
        importance sampling some of the on-policy episodes will be discarded
        and they should not be executed. `batch_size` can be less than or equal
        to the size of the input batch.

  Returns:
    CodeScoreInfo namedtuple instance. This holds not just the computed rewards,
    but additional information computed during code execution which can be used
    for debugging and monitoring. this includes: BF code strings, test cases
    the code was executed on, code outputs from those test cases, and reasons
    for success or failure.
  """
  code_strings = [
      ''.join([misc.bf_int2char(a) for a in action_sequence[:l]])
      for action_sequence, l in zip(batch_actions, episode_lengths)]
  if batch_size is None:
    batch_size = len(code_strings)
  else:
    assert batch_size <= len(code_strings)
    code_strings = code_strings[:batch_size]

  if isinstance(rl_batch.reward_fns, (list, tuple)):
    # reward_fns is a list of functions, same length as code_strings.
    assert len(rl_batch.reward_fns) >= batch_size
    r_fn_results = [
        rl_batch.reward_fns[i](code_strings[i]) for i in xrange(batch_size)]
  else:
    # reward_fns is allowed to be one function which processes a batch of code
    # strings. This is useful for efficiency and batch level computation.
    r_fn_results = rl_batch.reward_fns(code_strings)

  # Expecting that r_fn returns a list of rewards. Length of list equals
  # length of the code string (including EOS char).

  batch_rewards = [r.episode_rewards for r in r_fn_results]
  total_rewards = [sum(b) for b in batch_rewards]
  test_cases = [io_to_text(r.input_case, r.input_type) for r in r_fn_results]
  code_outputs = [io_to_text(r.code_output, r.output_type)
                  for r in r_fn_results]
  reasons = [r.reason for r in r_fn_results]
  return CodeScoreInfo(
      code_strings=code_strings,
      batch_rewards=batch_rewards,
      total_rewards=total_rewards,
      test_cases=test_cases,
      code_outputs=code_outputs,
      reasons=reasons)


def process_episodes(
    batch_rewards, episode_lengths, a2c=False, baselines=None,
    batch_values=None):
  """Compute REINFORCE targets.

  REINFORCE here takes the form:
  grad_t = grad[log(pi(a_t|c_t))*target_t]
  where c_t is context: i.e. RNN state or environment state (or both).

  Two types of targets are supported:
  1) Advantage actor critic (a2c).
  2) Vanilla REINFORCE with baseline.

  Args:
    batch_rewards: Rewards received in each episode in the batch. A numpy array
        of shape [batch_size, max_sequence_length]. Note, these are per-timestep
        rewards, not total reward.
    episode_lengths: Length of each episode. An iterable of length batch_size.
    a2c: A bool. Whether to compute a2c targets (True) or vanilla targets
        (False).
    baselines: If a2c is False, provide baselines for each timestep. This is a
        list (or indexable container) of length max_time. Note: baselines are
        shared across all episodes, which is why there is no batch dimension.
        It is up to the caller to update baselines accordingly.
    batch_values: If a2c is True, provide values computed by a value estimator.
        A numpy array of shape [batch_size, max_sequence_length].

  Returns:
    batch_targets: REINFORCE targets for each episode and timestep. A numpy
        array of shape [batch_size, max_sequence_length].
    batch_returns: Returns computed for each episode and timestep. This is for
        reference, and is not used in the REINFORCE gradient update (but was
        used to compute the targets). A numpy array of shape
        [batch_size, max_sequence_length].
  """
  num_programs = len(batch_rewards)
  assert num_programs <= len(episode_lengths)
  batch_returns = [None] * num_programs
  batch_targets = [None] * num_programs
  for i in xrange(num_programs):
    episode_length = episode_lengths[i]
    assert len(batch_rewards[i]) == episode_length
    # Compute target for each timestep.
    # If we are computing A2C:
    #    target_t = advantage_t = R_t - V(c_t)
    #    where V(c_t) is a learned value function (provided as `values`).
    # Otherwise:
    #    target_t = R_t - baselines[t]
    #    where `baselines` are provided.
    # In practice we use a more generalized formulation of advantage. See docs
    # for `discounted_advantage_and_rewards`.
    if a2c:
      # Compute advantage.
      assert batch_values is not None
      episode_values = batch_values[i, :episode_length]
      episode_rewards = batch_rewards[i]
      emp_val, gen_adv = rollout_lib.discounted_advantage_and_rewards(
          episode_rewards, episode_values, gamma=1.0, lambda_=1.0)
      batch_returns[i] = emp_val
      batch_targets[i] = gen_adv
    else:
      # Compute return for each timestep. See section 3 of
      # https://arxiv.org/pdf/1602.01783.pdf
      assert baselines is not None
      empirical_returns = rollout_lib.discount(batch_rewards[i], gamma=1.0)
      targets = [None] * episode_length
      for j in xrange(episode_length):
        targets[j] = empirical_returns[j] - baselines[j]
      batch_returns[i] = empirical_returns
      batch_targets[i] = targets
  batch_returns = utils.stack_pad(batch_returns, 0)
  if num_programs:
    batch_targets = utils.stack_pad(batch_targets, 0)
  else:
    batch_targets = np.array([], dtype=np.float32)

  return (batch_targets, batch_returns)

#This file: test_tasks_test.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Tests for test_tasks."""

import numpy as np
import tensorflow as tf

from single_task import misc  # brain coder
from single_task import test_tasks  # brain coder


def get_reward(reward_fn, candidate):
  return sum(reward_fn(misc.bf_tokens_to_string(candidate)).episode_rewards)


class TestTasksTest(tf.test.TestCase):

  def testHillClimbingTask(self):
    task = test_tasks.BasicTaskManager(test_tasks.HillClimbingTask())
    reward_fns = task.rl_batch(1)
    reward_fn = reward_fns[0]
    self.assertTrue(np.isclose(get_reward(reward_fn, [1, 2, 0]), 8 / 12.))
    self.assertTrue(np.isclose(get_reward(reward_fn, [1, 2, 2, 0]), 11 / 12.))
    self.assertTrue(np.isclose(get_reward(reward_fn, [1, 2, 3, 0]), 1.0))
    self.assertTrue(
        np.isclose(get_reward(reward_fn, [1, 2, 3, 4, 5, 2, 0]), 1. + 8 / 12.))
    self.assertTrue(
        np.isclose(get_reward(reward_fn, [1, 2, 3, 4, 5, 6, 0]), 2.0))
    self.assertTrue(
        np.isclose(get_reward(reward_fn, [1, 2, 3, 4, 5, 6, 1, 8, 3, 0]), 3.0))
    self.assertTrue(
        np.isclose(get_reward(reward_fn, [1, 2, 3, 4, 5, 6, 7, 8, 7, 0]), 3.0))
    self.assertTrue(
        np.isclose(get_reward(reward_fn, [1, 2, 3, 4, 5, 6, 1, 8, 3, 1, 0]),
                   3.0 - 4 / 12.))
    self.assertTrue(
        np.isclose(
            get_reward(reward_fn, [1, 2, 3, 4, 5, 6, 1, 8, 3, 1, 1, 1, 1, 0]),
            2.0))
    self.assertTrue(
        np.isclose(get_reward(reward_fn, [1, 2, 3, 4, 5, 6, 7, 8, 7, 3, 0]),
                   3.0 + 1 / 12.))
    self.assertTrue(
        np.isclose(
            get_reward(reward_fn, [1, 2, 3, 4, 5, 6, 7, 8, 7, 6, 5, 4, 3, 2, 1,
                                   8, 5, 1, 6, 4, 2, 1, 8, 3, 0]),
            8.0))
    self.assertTrue(
        np.isclose(
            get_reward(reward_fn, [1, 2, 3, 4, 5, 6, 7, 8, 7, 6, 5, 4, 3, 2, 1,
                                   8, 5, 1, 6, 4, 2, 1, 8, 3, 1, 1, 0]),
            8.0 - 8 / 12.))
    self.assertTrue(
        np.isclose(get_reward(reward_fn, [1, 2, 3, 4, 5, 6, 7, 8, 7, 6, 5, 4, 3,
                                          2, 1, 8, 5, 1, 6, 4, 2, 1, 8, 3, 1, 1,
                                          1, 1, 1, 1, 1, 0]),
                   7.0))


if __name__ == '__main__':
  tf.test.main()

#This file: ga_train.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Genetic algorithm for BF tasks.

Also contains the uniform random search algorithm.

Inspired by https://github.com/primaryobjects/AI-Programmer.
GA function code borrowed from https://github.com/DEAP/deap.
"""

import cPickle
import os
import sys
from time import sleep

from absl import flags
from absl import logging
import numpy as np
from six.moves import xrange
import tensorflow as tf

from common import utils  # brain coder
from single_task import data  # brain coder
from single_task import defaults  # brain coder
from single_task import ga_lib  # brain coder
from single_task import results_lib  # brain coder

FLAGS = flags.FLAGS


def define_tuner_hparam_space(hparam_space_type):
  """Define tunable hparams for grid search."""
  if hparam_space_type != 'ga':
    raise ValueError('Hparam space is not valid: "%s"' % hparam_space_type)
  return {
      'population_size': [10, 25, 50, 100, 500],
      'crossover_rate': [0.2, 0.5, 0.7, 0.9, 0.95],
      'mutation_rate': [0.01, 0.03, 0.05, 0.1, 0.15]}


def write_hparams_to_config(config, hparams, hparam_space_type):
  """Write hparams given by the tuner into the Config object."""
  if hparam_space_type != 'ga':
    raise ValueError('Hparam space is not valid: "%s"' % hparam_space_type)
  config.batch_size = hparams.population_size
  config.agent.crossover_rate = hparams.crossover_rate
  config.agent.mutation_rate = hparams.mutation_rate


class CheckpointWriter(object):
  """Manages loading and saving GA populations to disk.

  This object is used by the genetic algorithm to save progress periodically
  so that a recent population can be loaded from disk in the event of a restart.
  """

  def __init__(self, checkpoint_dir, population_size):
    self.checkpoint_file = os.path.join(checkpoint_dir, 'checkpoint.pickle')
    self.population_size = population_size

  def write(self, gen, population, halloffame):
    """Write GA state to disk.

    Overwrites previous saved state.

    Args:
      gen: Generation number.
      population: List of Individual objects.
      halloffame: Hall-of-fame buffer. Typically a priority queue.
    """
    raw = cPickle.dumps((gen, population, halloffame))
    with tf.gfile.FastGFile(self.checkpoint_file, 'w') as f:
      f.write(raw)

  def load(self):
    """Loads GA state from disk.

    Loads whatever is on disk, which will be whatever the most recent call
    to `write` wrote.

    Returns:
      gen: Generation number.
      population: List of Individual objects.
      halloffame: Hall-of-fame buffer. Typically a priority queue.
    """
    with tf.gfile.FastGFile(self.checkpoint_file, 'r') as f:
      raw = f.read()
    objs = cPickle.loads(raw)
    # Validate data.
    assert isinstance(objs, tuple) and len(objs) == 3, (
        'Expecting a 3-tuple, but got %s instead.' % (objs,))
    gen, population, halloffame = objs
    assert isinstance(gen, int), (
        'Expecting `gen` to be an integer, got %s' % (gen,))
    assert (
        isinstance(population, list)
        and len(population) == self.population_size
    ), (
        'Expecting `population` to be a list with size %d, got %s'
        % (self.population_size, population))
    assert halloffame is None or len(halloffame) == 2, (
        'Expecting hall-of-fame object to have length two, got length %d'
        % len(halloffame))
    logging.info('Loaded pop from checkpoint file: "%s".',
                 self.checkpoint_file)
    return gen, population, halloffame

  def has_checkpoint(self):
    """Checks if a checkpoint exists on disk, and if so returns True."""
    return tf.gfile.Exists(self.checkpoint_file)


def run_training(config=None, tuner=None, logdir=None, trial_name=None,  # pylint: disable=unused-argument
                 is_chief=True):
  """Do all training runs.

  This is the top level training function for policy gradient based models.
  Run this from the main function.

  Args:
    config: config_lib.Config instance containing global config (agent and
        environment hparams). If None, config will be parsed from FLAGS.config.
    tuner: (unused) A tuner instance. Leave as None if not tuning.
    logdir: Parent directory where all data from all runs will be written. If
        None, FLAGS.logdir will be used.
    trial_name: (unused) If tuning, set this to a unique string that identifies
        this trial. If `tuner` is not None, this also must be set.
    is_chief: True if this worker is the chief.

  Returns:
    List of results dicts which were written to disk. Each training run gets a
    results dict. Results dict contains metrics, i.e. (name, value) pairs which
    give information about the training run.

  Raises:
    ValueError: If FLAGS.num_workers does not divide FLAGS.num_repetitions.
    ValueError: If results dicts read from disk contain invalid data.
  """
  if not config:
    # If custom config is not given, get it from flags.
    config = defaults.default_config_with_updates(FLAGS.config)
  if not logdir:
    logdir = FLAGS.logdir

  if FLAGS.num_repetitions % FLAGS.num_workers != 0:
    raise ValueError('Number of workers must divide number of repetitions')
  num_local_reps = FLAGS.num_repetitions // FLAGS.num_workers
  logging.info('Running %d reps globally.', FLAGS.num_repetitions)
  logging.info('This worker will run %d local reps.', num_local_reps)
  if FLAGS.max_npe:
    max_generations = FLAGS.max_npe // config.batch_size
    logging.info('Max samples per rep: %d', FLAGS.max_npe)
    logging.info('Max generations per rep: %d', max_generations)
  else:
    max_generations = sys.maxint
    logging.info('Running unlimited generations.')

  assert FLAGS.num_workers > 0
  logging.info('Starting experiment. Directory: "%s"', logdir)
  results = results_lib.Results(logdir, FLAGS.task_id)
  local_results_list = results.read_this_shard()
  if local_results_list:
    if local_results_list[0]['max_npe'] != FLAGS.max_npe:
      raise ValueError(
          'Cannot resume training. Max-NPE changed. Was %s, now %s',
          local_results_list[0]['max_npe'], FLAGS.max_npe)
    if local_results_list[0]['max_global_repetitions'] != FLAGS.num_repetitions:
      raise ValueError(
          'Cannot resume training. Number of repetitions changed. Was %s, '
          'now %s',
          local_results_list[0]['max_global_repetitions'],
          FLAGS.num_repetitions)
  start_rep = len(local_results_list)

  for rep in xrange(start_rep, num_local_reps):
    global_rep = num_local_reps * FLAGS.task_id + rep
    logging.info(
        'Starting repetition: Rep = %d. (global rep = %d)',
        rep, global_rep)

    # Save data for each rep, like checkpoints, goes into separate folders.
    run_dir = os.path.join(logdir, 'run_%d' % global_rep)

    if not tf.gfile.IsDirectory(run_dir):
      tf.gfile.MakeDirs(run_dir)
    checkpoint_writer = CheckpointWriter(run_dir,
                                         population_size=config.batch_size)

    data_manager = data.DataManager(config, run_number=global_rep)
    task_eval_fn = ga_lib.make_task_eval_fn(data_manager.rl_task)

    if config.agent.algorithm == 'rand':
      logging.info('Running random search.')
      assert FLAGS.max_npe
      result = run_random_search(
          FLAGS.max_npe, run_dir, task_eval_fn, config.timestep_limit)
    else:
      assert config.agent.algorithm == 'ga'
      logging.info('Running genetic algorithm.')
      pop = ga_lib.make_population(
          ga_lib.random_individual(config.timestep_limit),
          n=config.batch_size)
      hof = utils.MaxUniquePriorityQueue(2)  # Hall of fame.
      result = ga_lib.ga_loop(
          pop,
          cxpb=config.agent.crossover_rate, mutpb=config.agent.mutation_rate,
          task_eval_fn=task_eval_fn,
          ngen=max_generations, halloffame=hof,
          checkpoint_writer=checkpoint_writer)

    logging.info('Finished rep. Num gens: %d', result.generations)

    results_dict = {
        'max_npe': FLAGS.max_npe,
        'batch_size': config.batch_size,
        'max_batches': FLAGS.max_npe // config.batch_size,
        'npe': result.num_programs,
        'max_global_repetitions': FLAGS.num_repetitions,
        'max_local_repetitions': num_local_reps,
        'code_solution': result.best_code if result.solution_found else '',
        'best_reward': result.reward,
        'num_batches': result.generations,
        'found_solution': result.solution_found,
        'task': data_manager.task_name,
        'global_rep': global_rep}
    logging.info('results_dict: %s', results_dict)
    results.append(results_dict)

  if is_chief:
    logging.info(
        'Worker is chief. Waiting for all workers to finish so that results '
        'can be reported to the tuner.')

    global_results_list, shard_stats = results.read_all(
        num_shards=FLAGS.num_workers)
    while not all(s.finished for s in shard_stats):
      logging.info(
          'Still waiting on these workers: %s',
          ', '.join(
              ['%d (%d reps left)'
               % (i, s.max_local_reps - s.num_local_reps_completed)
               for i, s in enumerate(shard_stats)
               if not s.finished]))
      sleep(60)
      global_results_list, shard_stats = results.read_all(
          num_shards=FLAGS.num_workers)

    logging.info(
        '%d results obtained. Chief worker is exiting the experiment.',
        len(global_results_list))

    return global_results_list


def run_random_search(max_num_programs, checkpoint_dir, task_eval_fn,
                      timestep_limit):
  """Run uniform random search routine.

  Randomly samples programs from a uniform distribution until either a valid
  program is found, or the maximum NPE is reached. Results are written to disk
  and returned.

  Args:
    max_num_programs: Maximum NPE (number of programs executed). If no solution
        is found after this many programs are tried, the run is stopped and
        considered a failure.
    checkpoint_dir: Where to save state during the run.
    task_eval_fn: Function that maps code string to result containing total
        reward and info about success.
    timestep_limit: Maximum length of code strings.

  Returns:
    ga_lib.GaResult namedtuple instance. This contains the best code and highest
    reward found.
  """
  checkpoint_file = os.path.join(checkpoint_dir, 'random_search.txt')
  num_programs_seen = 0
  found_solution = False
  best_code = ''
  best_reward = 0.0
  if tf.gfile.Exists(checkpoint_file):
    try:
      with tf.gfile.FastGFile(checkpoint_file, 'r') as f:
        lines = list(f)
        num_programs_seen = int(lines[0])
        found_solution = bool(int(lines[1]))
        if found_solution:
          best_code = lines[2]
          best_reward = float(lines[3])
    except:  # pylint: disable=bare-except
      pass

  while not found_solution and num_programs_seen < max_num_programs:
    if num_programs_seen % 1000 == 0:
      logging.info('num_programs_seen = %d', num_programs_seen)
      with tf.gfile.FastGFile(checkpoint_file, 'w') as f:
        f.write(str(num_programs_seen) + '\n')
        f.write(str(int(found_solution)) + '\n')

    code = np.random.choice(ga_lib.GENES, timestep_limit).tolist()
    res = task_eval_fn(code)
    found_solution = res.correct
    num_programs_seen += 1

    if found_solution:
      best_code = ''.join(code)
      best_reward = res.reward

  logging.info('num_programs_seen = %d', num_programs_seen)
  logging.info('found solution: %s', found_solution)
  with tf.gfile.FastGFile(checkpoint_file, 'w') as f:
    f.write(str(num_programs_seen) + '\n')
    f.write(str(int(found_solution)) + '\n')
    if found_solution:
      f.write(best_code + '\n')
      f.write(str(best_reward) + '\n')

  return ga_lib.GaResult(
      population=[], best_code=best_code, reward=best_reward,
      solution_found=found_solution, generations=num_programs_seen,
      num_programs=num_programs_seen, max_generations=max_num_programs,
      max_num_programs=max_num_programs)

#This file: aggregate_experiment_results.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

r"""This script crawls experiment directories for results and aggregates them.

Usage example:

MODELS_DIR="/tmp/models"
bazel run single_task:aggregate_experiment_results -- \
    --models_dir="$MODELS_DIR" \
    --max_npe="20M" \
    --task_list="add echo" \
    --model_types="[('topk', 'v0'), ('ga', 'v0')]" \
    --csv_file=/tmp/results_table.csv
"""

import ast
from collections import namedtuple
import csv
import os
import re
import StringIO
import sys

from absl import app
from absl import flags
import numpy as np
import tensorflow as tf

from single_task import misc  # brain coder
from single_task import results_lib  # brain coder

DEFAULT_MODELS = [('pg', 'v0'), ('topk', 'v0'), ('ga', 'v0'), ('rand', 'v0')]
DEFAULT_TASKS = [
    'reverse', 'remove-char', 'count-char', 'add', 'bool-logic', 'print-hello',
    'echo-twice', 'echo-thrice', 'copy-reverse', 'zero-cascade', 'cascade',
    'shift-left', 'shift-right', 'riffle', 'unriffle', 'middle-char',
    'remove-last', 'remove-last-two', 'echo-alternating', 'echo-half', 'length',
    'echo-second-seq', 'echo-nth-seq', 'substring', 'divide-2', 'dedup']

FLAGS = flags.FLAGS
flags.DEFINE_string(
    'models_dir', '',
    'Absolute path where results folders are found.')
flags.DEFINE_string(
    'exp_prefix', 'bf_rl_iclr',
    'Prefix for all experiment folders.')
flags.DEFINE_string(
    'max_npe', '5M',
    'String representation of max NPE of the experiments.')
flags.DEFINE_spaceseplist(
    'task_list', DEFAULT_TASKS,
    'List of task names separated by spaces. If empty string, defaults to '
    '`DEFAULT_TASKS`. These are the rows of the results table.')
flags.DEFINE_string(
    'model_types', str(DEFAULT_MODELS),
    'String representation of a python list of 2-tuples, each a model_type + '
    'job description pair. Descriptions allow you to choose among different '
    'runs of the same experiment. These are the columns of the results table.')
flags.DEFINE_string(
    'csv_file', '/tmp/results_table.csv',
    'Where to write results table. Format is CSV.')
flags.DEFINE_enum(
    'data', 'success_rates', ['success_rates', 'code'],
    'What type of data to aggregate.')


def make_csv_string(table):
  """Convert 2D list to CSV string."""
  s = StringIO.StringIO()
  writer = csv.writer(s)
  writer.writerows(table)
  value = s.getvalue()
  s.close()
  return value


def process_results(metrics):
  """Extract useful information from given metrics.

  Args:
    metrics: List of results dicts. These should have been written to disk by
        training jobs.

  Returns:
    Dict mapping stats names to values.

  Raises:
    ValueError: If max_npe or max_global_repetitions values are inconsistant
        across dicts in the `metrics` list.
  """
  count = len(metrics)
  success_count = 0
  total_npe = 0  # Counting NPE across all runs.
  success_npe = 0  # Counting NPE in successful runs only.
  max_npe = 0
  max_repetitions = 0
  for metric_dict in metrics:
    if not max_npe:
      max_npe = metric_dict['max_npe']
    elif max_npe != metric_dict['max_npe']:
      raise ValueError(
          'Invalid experiment. Different reps have different max-NPE settings.')
    if not max_repetitions:
      max_repetitions = metric_dict['max_global_repetitions']
    elif max_repetitions != metric_dict['max_global_repetitions']:
      raise ValueError(
          'Invalid experiment. Different reps have different num-repetition '
          'settings.')
    if metric_dict['found_solution']:
      success_count += 1
      success_npe += metric_dict['npe']
    total_npe += metric_dict['npe']
  stats = {}
  stats['max_npe'] = max_npe
  stats['max_repetitions'] = max_repetitions
  stats['repetitions'] = count
  stats['successes'] = success_count  # successful reps
  stats['failures'] = count - success_count  # failed reps
  stats['success_npe'] = success_npe
  stats['total_npe'] = total_npe
  if success_count:
    # Only successful runs counted.
    stats['avg_success_npe'] = stats['success_npe'] / float(success_count)
  else:
    stats['avg_success_npe'] = 0.0
  if count:
    stats['success_rate'] = success_count / float(count)
    stats['avg_total_npe'] = stats['total_npe'] / float(count)
  else:
    stats['success_rate'] = 0.0
    stats['avg_total_npe'] = 0.0

  return stats


ProcessedResults = namedtuple('ProcessedResults', ['metrics', 'processed'])


def get_results_for_experiment(
    models_dir, task_name, model_type='pg', max_npe='5M', desc='v0',
    name_prefix='bf_rl_paper', extra_desc=''):
  """Get and process results for a given experiment.

  An experiment is a set of runs with the same hyperparameters and environment.
  It is uniquely specified by a (task_name, model_type, max_npe) triple, as
  well as an optional description.

  We assume that each experiment has a folder with the same name as the job that
  ran the experiment. The name is computed by
  "%name_prefix%.%desc%-%max_npe%_%task_name%".

  Args:
    models_dir: Parent directory containing experiment folders.
    task_name: String name of task (the coding env). See code_tasks.py or
        run_eval_tasks.py
    model_type: Name of the algorithm, such as 'pg', 'topk', 'ga', 'rand'.
    max_npe: String SI unit representation of the maximum NPE threshold for the
        experiment. For example, "5M" means 5 million.
    desc: Description.
    name_prefix: Prefix of job names. Normally leave this as default.
    extra_desc: Optional extra description at the end of the job name.

  Returns:
    ProcessedResults namedtuple instance, containing
    metrics: Raw dicts read from disk.
    processed: Stats computed by `process_results`.

  Raises:
    ValueError: If max_npe in the metrics does not match NPE in the experiment
        folder name.
  """
  folder = name_prefix + '.{0}.{1}-{2}_{3}'.format(desc, model_type, max_npe,
                                                   task_name)
  if extra_desc:
    folder += '.' + extra_desc

  results = results_lib.Results(os.path.join(models_dir, folder))
  metrics, _ = results.read_all()
  processed = process_results(metrics)
  if (not np.isclose(processed['max_npe'], misc.si_to_int(max_npe))
      and processed['repetitions']):
    raise ValueError(
        'Invalid experiment. Max-NPE setting does not match expected max-NPE '
        'in experiment name.')
  return ProcessedResults(metrics=metrics, processed=processed)


BestCodeResults = namedtuple(
    'BestCodeResults',
    ['code', 'reward', 'npe', 'folder', 'finished', 'error'])


class BestCodeResultError(object):
  success = 0
  no_solution_found = 1
  experiment_does_not_exist = 2


def get_best_code_for_experiment(
    models_dir, task_name, model_type='pg', max_npe='5M', desc=0,
    name_prefix='bf_rl_paper', extra_desc=''):
  """Like `get_results_for_experiment`, but fetches the code solutions."""
  folder = name_prefix + '.{0}.{1}-{2}_{3}'.format(desc, model_type, max_npe,
                                                   task_name)
  if extra_desc:
    folder += '.' + extra_desc

  log_dir = os.path.join(models_dir, folder, 'logs')
  search_regex = r'^solutions_([0-9])+\.txt$'
  try:
    all_children = tf.gfile.ListDirectory(log_dir)
  except tf.errors.NotFoundError:
    return BestCodeResults(
        code=None, reward=0.0, npe=0, folder=folder, finished=False,
        error=BestCodeResultError.experiment_does_not_exist)
  solution_files = [
      fname for fname in all_children if re.search(search_regex, fname)]
  max_reward = 0.0
  npe = 0
  best_code = None
  for fname in solution_files:
    with tf.gfile.FastGFile(os.path.join(log_dir, fname), 'r') as reader:
      results = [ast.literal_eval(entry) for entry in reader]
    for res in results:
      if res['reward'] > max_reward:
        best_code = res['code']
        max_reward = res['reward']
        npe = res['npe']
  error = (
      BestCodeResultError.success if best_code
      else BestCodeResultError.no_solution_found)
  try:
    # If there is a status.txt file, check if it contains the status of the job.
    with tf.gfile.FastGFile(os.path.join(log_dir, 'status.txt'), 'r') as f:
      # Job is done, so mark this experiment as finished.
      finished = f.read().lower().strip() == 'done'
  except tf.errors.NotFoundError:
    # No status file has been written, so the experiment is not done. No need to
    # report an error here, because we do not require that experiment jobs write
    # out a status.txt file until they have finished.
    finished = False
  return BestCodeResults(
      code=best_code, reward=max_reward, npe=npe, folder=folder,
      finished=finished, error=error)


def make_results_table(
    models=None,
    tasks=None,
    max_npe='5M',
    name_prefix='bf_rl_paper',
    extra_desc='',
    models_dir='/tmp'):
  """Creates a table of results: algorithm + version by tasks.

  Args:
    models: The table columns. A list of (algorithm, desc) tuples.
    tasks: The table rows. List of task names.
    max_npe: String SI unit representation of the maximum NPE threshold for the
        experiment. For example, "5M" means 5 million. All entries in the table
        share the same max-NPE.
    name_prefix: Name prefix used in logging directory for the experiment.
    extra_desc: Extra description added to name of logging directory for the
        experiment.
    models_dir: Parent directory containing all experiment folders.

  Returns:
    A 2D list holding the table cells.
  """
  if models is None:
    models = DEFAULT_MODELS
  if tasks is None:
    tasks = DEFAULT_TASKS
  model_results = {}
  for model_type, desc in models:
    model_results[model_type] = {
        tname: get_results_for_experiment(
            models_dir, tname, model_type, max_npe, desc,
            name_prefix=name_prefix, extra_desc=extra_desc
        ).processed
        for tname in tasks}

  def info(stats):
    return [str(stats['repetitions']),
            '%.2f' % stats['success_rate'],
            str(int(stats['avg_total_npe']))]

  rows = [['max NPE: ' + max_npe]
          + misc.flatten([['{0} ({1})'.format(m, d), '', '']
                          for m, d in models])]
  rows.append(
      [''] + misc.flatten([['reps', 'success rate', 'avg NPE']
                           for _ in models]))
  for tname in tasks:
    rows.append(
        [tname]
        + misc.flatten([info(model_results[model][tname])
                        for model, _ in models]))

  return rows


def print_results_table(results_table):
  """Print human readable results table to stdout."""
  print('')
  print('=== Results Table ===')
  print('Format: # reps [success rate, avg total NPE]')

  def info_str(info_row):
    # num_runs (success_rate, avg_total_npe)
    if not info_row[0]:
      return '0'
    return '%s [%s, %s]' % (str(info_row[0]).ljust(2), info_row[1], info_row[2])

  nc = len(results_table[0])  # num cols
  out_table = [
      [results_table[0][0]] + [results_table[0][i] for i in range(1, nc, 3)]]
  for row in results_table[2:]:
    out_table.append([row[0]] + [info_str(row[i:i+3]) for i in range(1, nc, 3)])

  nc = len(out_table[0])  # num cols
  col_widths = [max(len(row[col]) for row in out_table) for col in range(nc)]

  table_string = ''
  for row in out_table:
    table_string += ''.join(
        [row[c].ljust(col_widths[c] + 2) for c in range(nc)]) + '\n'

  print(table_string)


def main(argv):
  del argv  # Unused.

  name_prefix = FLAGS.exp_prefix
  print('Experiments prefix: %s' % name_prefix)

  model_types = ast.literal_eval(FLAGS.model_types)

  if FLAGS.data == 'success_rates':
    results_table = make_results_table(
        models=model_types, tasks=FLAGS.task_list, max_npe=FLAGS.max_npe,
        models_dir=FLAGS.models_dir,
        name_prefix=name_prefix, extra_desc='')
    with tf.gfile.FastGFile(FLAGS.csv_file, 'w') as f:
      f.write(make_csv_string(results_table))

    print_results_table(results_table)
  else:
    # Best code
    print('* = experiment is still running')
    print('')
    print('=== Best Synthesized Code ===')
    for model_type, desc in model_types:
      print('%s (%s)' % (model_type, desc))
      sys.stdout.flush()
      for tname in FLAGS.task_list:
        res = get_best_code_for_experiment(
            FLAGS.models_dir, tname, model_type, FLAGS.max_npe, desc,
            name_prefix=name_prefix, extra_desc='')
        unfinished_mark = '' if res.finished else ' *'
        tname += unfinished_mark
        if res.error == BestCodeResultError.success:
          print('  %s' % tname)
          print('    %s' % res.code)
          print('    R=%.6f, NPE=%s' % (res.reward, misc.int_to_si(res.npe)))
        elif res.error == BestCodeResultError.experiment_does_not_exist:
          print('  Experiment does not exist. Check arguments.')
          print('  Experiment folder: %s' % res.folder)
          break
        else:
          print('  %s' % tname)
          print('    (none)')
        sys.stdout.flush()


if __name__ == '__main__':
  app.run(main)

#This file: tune.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

r"""Run grid search.

Look at launch_tuning.sh for details on how to tune at scale.

Usage example:
Tune with one worker on the local machine.

CONFIG="agent=c(algorithm='pg'),"
CONFIG+="env=c(task_cycle=['reverse-tune', 'remove-tune'])"
HPARAM_SPACE_TYPE="pg"
OUT_DIR="/tmp/bf_pg_tune"
MAX_NPE=5000000
NUM_REPETITIONS=50
rm -rf $OUT_DIR
mkdir $OUT_DIR
bazel run -c opt single_task:tune -- \
    --alsologtostderr \
    --config="$CONFIG" \
    --max_npe="$MAX_NPE" \
    --num_repetitions="$NUM_REPETITIONS" \
    --logdir="$OUT_DIR" \
    --summary_interval=1 \
    --model_v=0 \
    --hparam_space="$HPARAM_SPACE_TYPE" \
    --tuner_id=0 \
    --num_tuners=1 \
    2>&1 >"$OUT_DIR/tuner_0.log"
learning/brain/tensorboard/tensorboard.sh --port 12345 --logdir "$OUT_DIR"
"""

import ast
import os

from absl import app
from absl import flags
from absl import logging
import numpy as np
from six.moves import xrange
import tensorflow as tf

from single_task import defaults  # brain coder
from single_task import run as run_lib  # brain coder

FLAGS = flags.FLAGS
flags.DEFINE_integer(
    'tuner_id', 0,
    'The unique ID for this tuning worker.')
flags.DEFINE_integer(
    'num_tuners', 1,
    'How many tuners are there.')
flags.DEFINE_string(
    'hparam_space', 'default',
    'String name which denotes the hparam space to tune over. This is '
    'algorithm dependent.')
flags.DEFINE_string(
    'fixed_hparams', '',
    'HParams string. Used to fix hparams during tuning.')
flags.DEFINE_float(
    'success_rate_objective_weight', 1.0,
    'How much to weight success rate vs num programs seen. By default, only '
    'success rate is optimized (this is the setting used in the paper).')


def parse_hparams_string(hparams_str):
  hparams = {}
  for term in hparams_str.split(','):
    if not term:
      continue
    name, value = term.split('=')
    hparams[name.strip()] = ast.literal_eval(value)
  return hparams


def int_to_multibase(n, bases):
  digits = [0] * len(bases)
  for i, b in enumerate(bases):
    n, d = divmod(n, b)
    digits[i] = d
  return digits


def hparams_for_index(index, tuning_space):
  keys = sorted(tuning_space.keys())
  indices = int_to_multibase(index, [len(tuning_space[k]) for k in keys])
  return tf.contrib.training.HParams(
      **{k: tuning_space[k][i] for k, i in zip(keys, indices)})


def run_tuner_loop(ns):
  """Run tuning loop for this worker."""
  is_chief = FLAGS.task_id == 0
  tuning_space = ns.define_tuner_hparam_space(
      hparam_space_type=FLAGS.hparam_space)
  fixed_hparams = parse_hparams_string(FLAGS.fixed_hparams)
  for name, value in fixed_hparams.iteritems():
    tuning_space[name] = [value]
  tuning_space_size = np.prod([len(values) for values in tuning_space.values()])

  num_local_trials, remainder = divmod(tuning_space_size, FLAGS.num_tuners)
  if FLAGS.tuner_id < remainder:
    num_local_trials += 1
  starting_trial_id = (
      num_local_trials * FLAGS.tuner_id + min(remainder, FLAGS.tuner_id))

  logging.info('tuning_space_size: %d', tuning_space_size)
  logging.info('num_local_trials: %d', num_local_trials)
  logging.info('starting_trial_id: %d', starting_trial_id)

  for local_trial_index in xrange(num_local_trials):
    trial_config = defaults.default_config_with_updates(FLAGS.config)
    global_trial_index = local_trial_index + starting_trial_id
    trial_name = 'trial_' + str(global_trial_index)
    trial_dir = os.path.join(FLAGS.logdir, trial_name)
    hparams = hparams_for_index(global_trial_index, tuning_space)
    ns.write_hparams_to_config(
        trial_config, hparams, hparam_space_type=FLAGS.hparam_space)

    results_list = ns.run_training(
        config=trial_config, tuner=None, logdir=trial_dir, is_chief=is_chief,
        trial_name=trial_name)

    if not is_chief:
      # Only chief worker needs to write tuning results to disk.
      continue

    objective, metrics = compute_tuning_objective(
        results_list, hparams, trial_name, num_trials=tuning_space_size)
    logging.info('metrics:\n%s', metrics)
    logging.info('objective: %s', objective)
    logging.info('programs_seen_fraction: %s',
                 metrics['programs_seen_fraction'])
    logging.info('success_rate: %s', metrics['success_rate'])
    logging.info('success_rate_objective_weight: %s',
                 FLAGS.success_rate_objective_weight)

    tuning_results_file = os.path.join(trial_dir, 'tuning_results.txt')
    with tf.gfile.FastGFile(tuning_results_file, 'a') as writer:
      writer.write(str(metrics) + '\n')

    logging.info('Trial %s complete.', trial_name)


def compute_tuning_objective(results_list, hparams, trial_name, num_trials):
  """Compute tuning objective and metrics given results and trial information.

  Args:
    results_list: List of results dicts read from disk. These are written by
        workers.
    hparams: tf.contrib.training.HParams instance containing the hparams used
        in this trial (only the hparams which are being tuned).
    trial_name: Name of this trial. Used to create a trial directory.
    num_trials: Total number of trials that need to be run. This is saved in the
        metrics dict for future reference.

  Returns:
    objective: The objective computed for this trial. Choose the hparams for the
        trial with the largest objective value.
    metrics: Information about this trial. A dict.
  """
  found_solution = [r['found_solution'] for r in results_list]
  successful_program_counts = [
      r['npe'] for r in results_list if r['found_solution']]

  success_rate = sum(found_solution) / float(len(results_list))

  max_programs = FLAGS.max_npe  # Per run.
  all_program_counts = [
      r['npe'] if r['found_solution'] else max_programs
      for r in results_list]
  programs_seen_fraction = (
      float(sum(all_program_counts))
      / (max_programs * len(all_program_counts)))

  # min/max/avg stats are over successful runs.
  metrics = {
      'num_runs': len(results_list),
      'num_succeeded': sum(found_solution),
      'success_rate': success_rate,
      'programs_seen_fraction': programs_seen_fraction,
      'avg_programs': np.mean(successful_program_counts),
      'max_possible_programs_per_run': max_programs,
      'global_step': sum([r['num_batches'] for r in results_list]),
      'hparams': hparams.values(),
      'trial_name': trial_name,
      'num_trials': num_trials}

  # Report stats per tasks.
  tasks = [r['task'] for r in results_list]
  for task in set(tasks):
    task_list = [r for r in results_list if r['task'] == task]
    found_solution = [r['found_solution'] for r in task_list]
    successful_rewards = [
        r['best_reward'] for r in task_list
        if r['found_solution']]
    successful_num_batches = [
        r['num_batches']
        for r in task_list if r['found_solution']]
    successful_program_counts = [
        r['npe'] for r in task_list if r['found_solution']]
    metrics_append = {
        task + '__num_runs': len(task_list),
        task + '__num_succeeded': sum(found_solution),
        task + '__success_rate': (
            sum(found_solution) / float(len(task_list)))}
    metrics.update(metrics_append)
    if any(found_solution):
      metrics_append = {
          task + '__min_reward': min(successful_rewards),
          task + '__max_reward': max(successful_rewards),
          task + '__avg_reward': np.median(successful_rewards),
          task + '__min_programs': min(successful_program_counts),
          task + '__max_programs': max(successful_program_counts),
          task + '__avg_programs': np.mean(successful_program_counts),
          task + '__min_batches': min(successful_num_batches),
          task + '__max_batches': max(successful_num_batches),
          task + '__avg_batches': np.mean(successful_num_batches)}
      metrics.update(metrics_append)

  # Objective will be maximized.
  # Maximize success rate, minimize num programs seen.
  # Max objective is always 1.
  weight = FLAGS.success_rate_objective_weight
  objective = (
      weight * success_rate
      + (1 - weight) * (1 - programs_seen_fraction))
  metrics['objective'] = objective

  return objective, metrics


def main(argv):
  del argv

  logging.set_verbosity(FLAGS.log_level)

  if not FLAGS.logdir:
    raise ValueError('logdir flag must be provided.')
  if FLAGS.num_workers <= 0:
    raise ValueError('num_workers flag must be greater than 0.')
  if FLAGS.task_id < 0:
    raise ValueError('task_id flag must be greater than or equal to 0.')
  if FLAGS.task_id >= FLAGS.num_workers:
    raise ValueError(
        'task_id flag must be strictly less than num_workers flag.')
  if FLAGS.num_tuners <= 0:
    raise ValueError('num_tuners flag must be greater than 0.')
  if FLAGS.tuner_id < 0:
    raise ValueError('tuner_id flag must be greater than or equal to 0.')
  if FLAGS.tuner_id >= FLAGS.num_tuners:
    raise ValueError(
        'tuner_id flag must be strictly less than num_tuners flag.')

  ns, _ = run_lib.get_namespace(FLAGS.config)
  run_tuner_loop(ns)


if __name__ == '__main__':
  app.run(main)

#This file: results_lib_test.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Tests for results_lib."""

import contextlib
import os
import shutil
import tempfile
from six.moves import xrange
import tensorflow as tf

from single_task import results_lib  # brain coder


@contextlib.contextmanager
def temporary_directory(suffix='', prefix='tmp', base_path=None):
  """A context manager to create a temporary directory and clean up on exit.

  The parameters are the same ones expected by tempfile.mkdtemp.
  The directory will be securely and atomically created.
  Everything under it will be removed when exiting the context.

  Args:
    suffix: optional suffix.
    prefix: options prefix.
    base_path: the base path under which to create the temporary directory.
  Yields:
    The absolute path of the new temporary directory.
  """
  temp_dir_path = tempfile.mkdtemp(suffix, prefix, base_path)
  try:
    yield temp_dir_path
  finally:
    try:
      shutil.rmtree(temp_dir_path)
    except OSError as e:
      if e.message == 'Cannot call rmtree on a symbolic link':
        # Interesting synthetic exception made up by shutil.rmtree.
        # Means we received a symlink from mkdtemp.
        # Also means must clean up the symlink instead.
        os.unlink(temp_dir_path)
      else:
        raise


def freeze(dictionary):
  """Convert dict to hashable frozenset."""
  return frozenset(dictionary.iteritems())


class ResultsLibTest(tf.test.TestCase):

  def testResults(self):
    with temporary_directory() as logdir:
      results_obj = results_lib.Results(logdir)
      self.assertEqual(results_obj.read_this_shard(), [])
      results_obj.append(
          {'foo': 1.5, 'bar': 2.5, 'baz': 0})
      results_obj.append(
          {'foo': 5.5, 'bar': -1, 'baz': 2})
      self.assertEqual(
          results_obj.read_this_shard(),
          [{'foo': 1.5, 'bar': 2.5, 'baz': 0},
           {'foo': 5.5, 'bar': -1, 'baz': 2}])

  def testShardedResults(self):
    with temporary_directory() as logdir:
      n = 4  # Number of shards.
      results_objs = [
          results_lib.Results(logdir, shard_id=i) for i in xrange(n)]
      for i, robj in enumerate(results_objs):
        robj.append({'foo': i, 'bar': 1 + i * 2})
      results_list, _ = results_objs[0].read_all()

      # Check results. Order does not matter here.
      self.assertEqual(
          set(freeze(r) for r in results_list),
          set(freeze({'foo': i, 'bar': 1 + i * 2}) for i in xrange(n)))


if __name__ == '__main__':
  tf.test.main()

#This file: test_tasks.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Tasks that test correctness of algorithms."""

from six.moves import xrange
from common import reward as reward_lib  # brain coder
from single_task import misc  # brain coder


class BasicTaskManager(object):
  """Wraps a generic reward function."""

  def __init__(self, reward_fn):
    self.reward_fn = reward_fn
    self.good_reward = 1.0

  def _score_string(self, string):
    actions = misc.bf_string_to_tokens(string)
    reward, correct = self.reward_fn(actions)
    return misc.RewardInfo(
        episode_rewards=[0.0] * (len(string) - 1) + [reward],
        input_case=None,
        correct_output=None,
        code_output=actions,
        input_type=None,
        output_type=misc.IOType.integer,
        reason='correct' if correct else 'wrong')

  def rl_batch(self, batch_size):
    reward_fns = [self._score_string] * batch_size
    return reward_fns


class Trie(object):
  """Trie for sequences."""
  EOS = ()

  def __init__(self):
    self.trie = {}

  def insert(self, sequence):
    d = self.trie
    for e in sequence:
      if e not in d:
        d[e] = {}
      d = d[e]
    d[self.EOS] = True   # Terminate sequence.

  def prefix_match(self, sequence):
    """Return prefix of `sequence` which exists in the trie."""
    d = self.trie
    index = 0
    for i, e in enumerate(sequence + [self.EOS]):
      index = i
      if e in d:
        d = d[e]
        if e == self.EOS:
          return sequence, True
      else:
        break
    return sequence[:index], False

  def next_choices(self, sequence):
    d = self.trie
    for e in sequence:
      if e in d:
        d = d[e]
      else:
        raise ValueError('Sequence not a prefix: %s' % (sequence,))
    return d.keys()


class HillClimbingTask(object):
  """Simple task that tests reward hill climbing ability.

  There are a set of paths (sequences of tokens) which are rewarded. The total
  reward for a path is proportional to its length, so the longest path is the
  target. Shorter paths can be dead ends.
  """

  def __init__(self):
    # Paths are sequences of sub-sequences. Here we form unique sub-sequences
    # out of 3 arbitrary ints. We use sub-sequences instead of single entities
    # to make the task harder by making the episodes last longer, i.e. more
    # for the agent to remember.
    a = (1, 2, 3)
    b = (4, 5, 6)
    c = (7, 8, 7)
    d = (6, 5, 4)
    e = (3, 2, 1)
    f = (8, 5, 1)
    g = (6, 4, 2)
    h = (1, 8, 3)
    self.paths = Trie()
    self.paths.insert([a, b, h])
    self.paths.insert([a, b, c, d, e, f, g, h])
    self.paths.insert([a, b, c, d, e, b, a])
    self.paths.insert([a, b, g, h])
    self.paths.insert([a, e, f, g])
    self.correct_sequence = misc.flatten([a, b, c, d, e, f, g, h])

    def distance_fn(a, b):
      len_diff = abs(len(a) - len(b))
      return sum(reward_lib.mod_abs_diff(ai - 1, bi - 1, 8)
                 for ai, bi in zip(a, b)) + len_diff * 4  # 8 / 2 = 4
    self.distance_fn = distance_fn

  def __call__(self, actions):
    # Compute reward for action sequence.
    actions = [a for a in actions if a > 0]
    sequence = [tuple(actions[i: i + 3]) for i in xrange(0, len(actions), 3)]
    prefix, complete = self.paths.prefix_match(sequence)
    if complete:
      return float(len(prefix)), actions == self.correct_sequence
    if len(prefix) == len(sequence):
      return float(len(prefix)), False
    next_pred = sequence[len(prefix)]
    choices = self.paths.next_choices(prefix)
    if choices == [()]:
      return (len(prefix) - len(next_pred) / 3.0), False
    min_dist = min(self.distance_fn(c, next_pred) for c in choices)
    # +1 reward for each element in the sequence correct, plus fraction torwards
    # closest next element.
    # Maximum distance possible is num_actions * base / 2 = 3 * 8 / 2 = 12
    return (len(prefix) + (1 - min_dist / 12.0)), False

#This file: pg_agent_test.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Tests for pg_agent."""

from collections import Counter

from absl import logging
import numpy as np
from six.moves import xrange
import tensorflow as tf

from common import utils  # brain coder
from single_task import data  # brain coder
from single_task import defaults  # brain coder
from single_task import misc  # brain coder
from single_task import pg_agent as agent_lib  # brain coder
from single_task import pg_train  # brain coder


# Symmetric mean absolute percentage error (SMAPE).
# https://en.wikipedia.org/wiki/Symmetric_mean_absolute_percentage_error
def smape(a, b):
  return 2.0 * abs(a - b) / float(a + b)


def onehot(dim, num_dims):
  value = np.zeros(num_dims, dtype=np.float32)
  value[dim] = 1
  return value


def random_sequence(max_length, num_tokens, eos=0):
  length = np.random.randint(1, max_length - 1)
  return np.append(np.random.randint(1, num_tokens, length), eos)


def repeat_and_pad(v, rep, total_len):
  return [v] * rep + [0.0] * (total_len - rep)


class AgentTest(tf.test.TestCase):

  def testProcessEpisodes(self):
    batch_size = 3

    def reward_fn(code_string):
      return misc.RewardInfo(
          episode_rewards=[float(ord(c)) for c in code_string],
          input_case=[],
          correct_output=[],
          code_output=[],
          input_type=misc.IOType.integer,
          output_type=misc.IOType.integer,
          reason='none')

    rl_batch = data.RLBatch(
        reward_fns=[reward_fn for _ in range(batch_size)],
        batch_size=batch_size,
        good_reward=10.0)
    batch_actions = np.asarray([
        [4, 5, 3, 6, 8, 1, 0, 0],
        [1, 2, 3, 4, 0, 0, 0, 0],
        [8, 7, 6, 5, 4, 3, 2, 1]], dtype=np.int32)
    batch_values = np.asarray([
        [0, 1, 2, 1, 0, 1, 1, 0],
        [0, 2, 1, 2, 1, 0, 0, 0],
        [0, 1, 1, 0, 0, 0, 1, 1]], dtype=np.float32)
    episode_lengths = np.asarray([7, 5, 8], dtype=np.int32)

    scores = agent_lib.compute_rewards(
        rl_batch, batch_actions, episode_lengths)
    batch_targets, batch_returns = agent_lib.process_episodes(
        scores.batch_rewards, episode_lengths, a2c=True,
        batch_values=batch_values)
    self.assertEqual(
        [[473.0, 428.0, 337.0, 294.0, 201.0, 157.0, 95.0, 0.0],
         [305.0, 243.0, 183.0, 140.0, 95.0, 0.0, 0.0, 0.0],
         [484.0, 440.0, 394.0, 301.0, 210.0, 165.0, 122.0, 62.0]],
        batch_returns.tolist())
    self.assertEqual(
        [[473.0, 427.0, 335.0, 293.0, 201.0, 156.0, 94.0, 0.0],
         [305.0, 241.0, 182.0, 138.0, 94.0, 0.0, 0.0, 0.0],
         [484.0, 439.0, 393.0, 301.0, 210.0, 165.0, 121.0, 61.0]],
        batch_targets.tolist())

  def testVarUpdates(self):
    """Tests that variables get updated as expected.

    For the RL update, check that gradients are non-zero and that the global
    model gets updated.
    """
    config = defaults.default_config_with_updates(
        'env=c(task="reverse"),'
        'agent=c(algorithm="pg",eos_token=True,optimizer="sgd",lr=1.0)')
    lr = config.agent.lr

    tf.reset_default_graph()
    trainer = pg_train.AsyncTrainer(
        config, task_id=0, ps_tasks=0, num_workers=1)
    global_init_op = tf.variables_initializer(
        tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, 'global'))
    with tf.Session() as sess:
      sess.run(global_init_op)  # Initialize global copy.
      trainer.initialize(sess)
      model = trainer.model
      global_vars = sess.run(trainer.global_model.trainable_variables)
      local_vars = sess.run(model.trainable_variables)

      # Make sure names match.
      g_prefix = 'global/'
      l_prefix = 'local/'
      for g, l in zip(trainer.global_model.trainable_variables,
                      model.trainable_variables):
        self.assertEqual(g.name[len(g_prefix):], l.name[len(l_prefix):])

      # Assert that shapes and values are the same between global and local
      # models.
      for g, l in zip(global_vars, local_vars):
        self.assertEqual(g.shape, l.shape)
        self.assertTrue(np.array_equal(g, l))

      # Make all gradients dense tensors.
      for param, grad in model.gradients_dict.items():
        if isinstance(grad, tf.IndexedSlices):
          # Converts to dense tensor.
          model.gradients_dict[param] = tf.multiply(grad, 1.0)

      # Perform update.
      results = model.update_step(
          sess, trainer.data_manager.sample_rl_batch(), trainer.train_op,
          trainer.global_step, return_gradients=True)
      grads_dict = results.gradients_dict
      for grad in grads_dict.values():
        self.assertIsNotNone(grad)
        self.assertTrue(np.count_nonzero(grad) > 0)
      global_update = sess.run(trainer.global_model.trainable_variables)
      for tf_var, var_before, var_after in zip(
          model.trainable_variables, local_vars, global_update):
        # Check that the params were updated.
        self.assertTrue(np.allclose(
            var_after,
            var_before - grads_dict[tf_var] * lr))

      # Test that global to local sync works.
      sess.run(trainer.sync_op)
      global_vars = sess.run(trainer.global_model.trainable_variables)
      local_vars = sess.run(model.trainable_variables)
      for l, g in zip(local_vars, global_vars):
        self.assertTrue(np.allclose(l, g))

  def testMonteCarloGradients(self):
    """Test Monte Carlo estimate of REINFORCE gradient.

    Test that the Monte Carlo estimate of the REINFORCE gradient is
    approximately equal to the true gradient. We compute the true gradient for a
    toy environment with a very small action space.

    Similar to section 5 of https://arxiv.org/pdf/1505.00521.pdf.
    """
    # Test may have different outcome on different machines due to different
    # rounding behavior of float arithmetic.
    tf.reset_default_graph()
    tf.set_random_seed(12345678987654321)
    np.random.seed(1294024302)
    max_length = 2
    num_tokens = misc.bf_num_tokens()
    eos = misc.BF_EOS_INT
    assert eos == 0
    def sequence_iterator(max_length):
      """Iterates through all sequences up to the given length."""
      yield [eos]
      for a in xrange(1, num_tokens):
        if max_length > 1:
          for sub_seq in sequence_iterator(max_length - 1):
            yield [a] + sub_seq
        else:
          yield [a]
    actions = list(sequence_iterator(max_length))

    # This batch contains all possible episodes up to max_length.
    actions_batch = utils.stack_pad(actions, 0)
    lengths_batch = [len(s) for s in actions]

    reward_map = {tuple(a): np.random.randint(-1, 7) for a in actions_batch}
    # reward_map = {tuple(a): np.random.normal(3, 1)
    #               for a in actions_batch}  # normal distribution
    # reward_map = {tuple(a): 1.0
    #               for a in actions_batch}  # expected reward is 1

    n = 100000  # MC sample size.
    config = defaults.default_config_with_updates(
        'env=c(task="print"),'
        'agent=c(algorithm="pg",optimizer="sgd",lr=1.0,ema_baseline_decay=0.99,'
        'entropy_beta=0.0,topk_loss_hparam=0.0,regularizer=0.0,'
        'policy_lstm_sizes=[10],eos_token=True),'
        'batch_size='+str(n)+',timestep_limit='+str(max_length))

    dtype = tf.float64
    trainer = pg_train.AsyncTrainer(
        config, task_id=0, ps_tasks=0, num_workers=1, dtype=dtype)
    model = trainer.model
    actions_ph = model.actions
    lengths_ph = model.adjusted_lengths
    multipliers_ph = model.policy_multipliers

    global_init_op = tf.variables_initializer(
        tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, 'global'))
    with tf.Session() as sess, sess.graph.as_default():
      sess.run(global_init_op)  # Initialize global copy.
      trainer.initialize(sess)

      # Compute exact gradients.
      # exact_grads = sum(P(a) * grad(log P(a)) * R(a) for a in actions_batch)
      true_loss_unnormalized = 0.0
      exact_grads = [np.zeros(v.shape) for v in model.trainable_variables]
      episode_probs_map = {}
      grads_map = {}
      for a_idx in xrange(len(actions_batch)):
        a = actions_batch[a_idx]
        grads_result, probs_result, loss = sess.run(
            [model.dense_unclipped_grads, model.chosen_probs, model.loss],
            {actions_ph: [a],
             lengths_ph: [lengths_batch[a_idx]],
             multipliers_ph: [
                 repeat_and_pad(reward_map[tuple(a)],
                                lengths_batch[a_idx],
                                max_length)]})
        # Take product over time axis.
        episode_probs_result = np.prod(probs_result[0, :lengths_batch[a_idx]])
        for i in range(0, len(exact_grads)):
          exact_grads[i] += grads_result[i] * episode_probs_result
        episode_probs_map[tuple(a)] = episode_probs_result
        reward_map[tuple(a)] = reward_map[tuple(a)]
        grads_map[tuple(a)] = grads_result
        true_loss_unnormalized += loss
      # Normalize loss. Since each episode is feed into the model one at a time,
      # normalization needs to be done manually.
      true_loss = true_loss_unnormalized / float(len(actions_batch))

      # Compute Monte Carlo gradients.
      # E_a~P[grad(log P(a)) R(a)] is aprox. eq. to
      # sum(grad(log P(a)) R(a) for a in actions_sampled_from_P) / n
      # where len(actions_sampled_from_P) == n.
      #
      # In other words, sample from the policy and compute the gradients of the
      # log probs weighted by the returns. This will excersize the code in
      # agent.py
      sampled_actions, sampled_lengths = sess.run(
          [model.sampled_tokens, model.episode_lengths])
      pi_multipliers = [
          repeat_and_pad(reward_map[tuple(a)], l, max_length)
          for a, l in zip(sampled_actions, sampled_lengths)]
      mc_grads_unnormalized, sampled_probs, mc_loss_unnormalized = sess.run(
          [model.dense_unclipped_grads, model.chosen_probs, model.loss],
          {actions_ph: sampled_actions,
           multipliers_ph: pi_multipliers,
           lengths_ph: sampled_lengths})
      # Loss is already normalized across the minibatch, so no normalization
      # is needed.
      mc_grads = mc_grads_unnormalized
      mc_loss = mc_loss_unnormalized

    # Make sure true loss and MC loss are similar.
    loss_error = smape(true_loss, mc_loss)
    self.assertTrue(loss_error < 0.15, msg='actual: %s' % loss_error)

    # Check that probs computed for episodes sampled from the model are the same
    # as the recorded true probs.
    for i in range(100):
      acs = tuple(sampled_actions[i].tolist())
      sampled_prob = np.prod(sampled_probs[i, :sampled_lengths[i]])
      self.assertTrue(np.isclose(episode_probs_map[acs], sampled_prob))

    # Make sure MC estimates of true probs are close.
    counter = Counter(tuple(e) for e in sampled_actions)
    for acs, count in counter.iteritems():
      mc_prob = count / float(len(sampled_actions))
      true_prob = episode_probs_map[acs]
      error = smape(mc_prob, true_prob)
      self.assertTrue(
          error < 0.15,
          msg='actual: %s; count: %s; mc_prob: %s; true_prob: %s'
          % (error, count, mc_prob, true_prob))

    # Manually recompute MC gradients and make sure they match MC gradients
    # computed in TF.
    mc_grads_recompute = [np.zeros(v.shape) for v in model.trainable_variables]
    for i in range(n):
      acs = tuple(sampled_actions[i].tolist())
      for i in range(0, len(mc_grads_recompute)):
        mc_grads_recompute[i] += grads_map[acs][i]
    for i in range(0, len(mc_grads_recompute)):
      self.assertTrue(np.allclose(mc_grads[i], mc_grads_recompute[i] / n))

    # Check angle between gradients as fraction of pi.
    for index in range(len(mc_grads)):
      v1 = mc_grads[index].reshape(-1)
      v2 = exact_grads[index].reshape(-1)
      # angle = arccos(v1 . v2 / (|v1|*|v2|))
      angle_rad = np.arccos(
          np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
      logging.info('angle / pi: %s', angle_rad / np.pi)
      angle_frac = angle_rad / np.pi
      self.assertTrue(angle_frac < 0.02, msg='actual: %s' % angle_frac)
    # Check norms.
    for index in range(len(mc_grads)):
      v1_norm = np.linalg.norm(mc_grads[index].reshape(-1))
      v2_norm = np.linalg.norm(exact_grads[index].reshape(-1))
      error = smape(v1_norm, v2_norm)
      self.assertTrue(error < 0.02, msg='actual: %s' % error)

    # Check expected rewards.
    # E_a~P[R(a)] approx eq sum(P(a) * R(a) for a in actions)
    mc_expected_reward = np.mean(
        [reward_map[tuple(a)] for a in sampled_actions])
    exact_expected_reward = np.sum(
        [episode_probs_map[k] * reward_map[k] for k in reward_map])
    error = smape(mc_expected_reward, exact_expected_reward)
    self.assertTrue(error < 0.005, msg='actual: %s' % angle_frac)

  def testNumericalGradChecking(self):
    # Similar to
    # http://ufldl.stanford.edu/wiki/index.php/Gradient_checking_and_advanced_optimization.
    epsilon = 1e-4
    eos = misc.BF_EOS_INT
    self.assertEqual(0, eos)
    config = defaults.default_config_with_updates(
        'env=c(task="print"),'
        'agent=c(algorithm="pg",optimizer="sgd",lr=1.0,ema_baseline_decay=0.99,'
        'entropy_beta=0.0,topk_loss_hparam=0.0,policy_lstm_sizes=[10],'
        'eos_token=True),'
        'batch_size=64')
    dtype = tf.float64
    tf.reset_default_graph()
    tf.set_random_seed(12345678987654321)
    np.random.seed(1294024302)
    trainer = pg_train.AsyncTrainer(
        config, task_id=0, ps_tasks=0, num_workers=1, dtype=dtype)
    model = trainer.model
    actions_ph = model.actions
    lengths_ph = model.adjusted_lengths
    multipliers_ph = model.policy_multipliers
    loss = model.pi_loss
    global_init_op = tf.variables_initializer(
        tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, 'global'))

    assign_add_placeholders = [None] * len(model.trainable_variables)
    assign_add_ops = [None] * len(model.trainable_variables)
    param_shapes = [None] * len(model.trainable_variables)
    for i, param in enumerate(model.trainable_variables):
      param_shapes[i] = param.get_shape().as_list()
      assign_add_placeholders[i] = tf.placeholder(dtype,
                                                  np.prod(param_shapes[i]))
      assign_add_ops[i] = param.assign_add(
          tf.reshape(assign_add_placeholders[i], param_shapes[i]))

    with tf.Session() as sess:
      sess.run(global_init_op)  # Initialize global copy.
      trainer.initialize(sess)

      actions_raw = [random_sequence(10, 9) for _ in xrange(16)]
      actions_batch = utils.stack_pad(actions_raw, 0)
      lengths_batch = [len(l) for l in actions_raw]
      feed = {actions_ph: actions_batch,
              multipliers_ph: np.ones_like(actions_batch),
              lengths_ph: lengths_batch}

      estimated_grads = [None] * len(model.trainable_variables)
      for i, param in enumerate(model.trainable_variables):
        param_size = np.prod(param_shapes[i])
        estimated_grads[i] = np.zeros(param_size, dtype=np.float64)
        for index in xrange(param_size):
          e = onehot(index, param_size) * epsilon
          sess.run(assign_add_ops[i],
                   {assign_add_placeholders[i]: e})
          j_plus = sess.run(loss, feed)
          sess.run(assign_add_ops[i],
                   {assign_add_placeholders[i]: -2 * e})
          j_minus = sess.run(loss, feed)
          sess.run(assign_add_ops[i],
                   {assign_add_placeholders[i]: e})
          estimated_grads[i][index] = (j_plus - j_minus) / (2 * epsilon)
        estimated_grads[i] = estimated_grads[i].reshape(param_shapes[i])

      analytic_grads = sess.run(model.dense_unclipped_grads, feed)

      for g1, g2 in zip(estimated_grads[1:], analytic_grads[1:]):
        logging.info('norm (g1-g2): %s', np.abs(g1 - g2).mean())
        self.assertTrue(np.allclose(g1, g2))


if __name__ == '__main__':
  tf.test.main()

#This file: defaults.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Default configuration for agent and environment."""

from absl import logging

from common import config_lib  # brain coder


def default_config():
  return config_lib.Config(
      agent=config_lib.OneOf(
          [config_lib.Config(
              algorithm='pg',
              policy_lstm_sizes=[35,35],
              # Set value_lstm_sizes to None to share weights with policy.
              value_lstm_sizes=[35,35],
              obs_embedding_size=10,
              grad_clip_threshold=10.0,
              param_init_factor=1.0,
              lr=5e-5,
              pi_loss_hparam=1.0,
              vf_loss_hparam=0.5,
              entropy_beta=1e-2,
              regularizer=0.0,
              softmax_tr=1.0,  # Reciprocal temperature.
              optimizer='rmsprop',  # 'adam', 'sgd', 'rmsprop'
              topk=0,  # Top-k unique codes will be stored.
              topk_loss_hparam=0.0,  # off policy loss multiplier.
              # Uniformly sample this many episodes from topk buffer per batch.
              # If topk is 0, this has no effect.
              topk_batch_size=1,
              # Exponential moving average baseline for REINFORCE.
              # If zero, A2C is used.
              # If non-zero, should be close to 1, like .99, .999, etc.
              ema_baseline_decay=0.99,
              # Whether agent can emit EOS token. If true, agent can emit EOS
              # token which ends the episode early (ends the sequence).
              # If false, agent must emit tokens until the timestep limit is
              # reached. e.g. True means variable length code, False means fixed
              # length code.
              # WARNING: Making this false slows things down.
              eos_token=False,
              replay_temperature=1.0,
              # Replay probability. 1 = always replay, 0 = always on policy.
              alpha=0.0,
              # Whether to normalize importance weights in each minibatch.
              iw_normalize=True),
           config_lib.Config(
              algorithm='ga',
              crossover_rate=0.99,
              mutation_rate=0.086),
           config_lib.Config(
              algorithm='rand')],
          algorithm='pg',
      ),
      env=config_lib.Config(
          # If True, task-specific settings are not needed.
          task='',  # 'print', 'echo', 'reverse', 'remove', ...
          task_cycle=[],  # If non-empty, reptitions will cycle through tasks.
          task_kwargs='{}',  # Python dict literal.
          task_manager_config=config_lib.Config(
              # Reward recieved per test case. These bonuses will be scaled
              # based on how many test cases there are.
              correct_bonus=2.0,  # Bonus for code getting correct answer.
              code_length_bonus=1.0),  # Maximum bonus for short code.
          correct_syntax=False,
      ),
      batch_size=64,
      timestep_limit=32)


def default_config_with_updates(config_string, do_logging=True):
  if do_logging:
    logging.info('Config string: "%s"', config_string)
  config = default_config()
  config.strict_update(config_lib.Config.parse(config_string))
  if do_logging:
    logging.info('Config:\n%s', config.pretty_str())
  return config

#This file: aggregate_tuning_results.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

r"""After running tuning, use this script to aggregate the results.

Usage:

OUT_DIR="<my_tuning_dir>"
bazel run -c opt single_task:aggregate_tuning_results -- \
    --alsologtostderr \
    --tuning_dir="$OUT_DIR"
"""

import ast
import os

from absl import app
from absl import flags
import tensorflow as tf


FLAGS = flags.FLAGS
flags.DEFINE_string(
    'tuning_dir', '',
    'Absolute path where results tuning trial folders are found.')


def main(argv):
  del argv  # Unused.

  try:
    trial_dirs = tf.gfile.ListDirectory(FLAGS.tuning_dir)
  except tf.errors.NotFoundError:
    print('Tuning directory %s does not exist.' % (FLAGS.tuning_dir,))
    return

  metrics = []
  for trial_dir in trial_dirs:
    tuning_results_file = os.path.join(
        FLAGS.tuning_dir, trial_dir, 'tuning_results.txt')
    if tf.gfile.Exists(tuning_results_file):
      with tf.gfile.FastGFile(tuning_results_file, 'r') as reader:
        for line in reader:
          metrics.append(ast.literal_eval(line.replace(': nan,', ': 0.0,')))

  if not metrics:
    print('No trials found.')
    return

  num_trials = [m['num_trials'] for m in metrics]
  assert all(n == num_trials[0] for n in num_trials)
  num_trials = num_trials[0]
  print('Found %d completed trials out of %d' % (len(metrics), num_trials))

  # Sort by objective descending.
  sorted_trials = sorted(metrics, key=lambda m: -m['objective'])

  for i, metrics in enumerate(sorted_trials):
    hparams = metrics['hparams']
    keys = sorted(hparams.keys())
    print(
        str(i).ljust(4) + ': '
        + '{0:.2f}'.format(metrics['objective']).ljust(10)
        + '['
        + ','.join(['{}={}'.format(k, hparams[k]).ljust(24) for k in keys])
        + ']')


if __name__ == '__main__':
  app.run(main)

#This file: code_tasks_test.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Tests for code_tasks."""

import numpy as np
import tensorflow as tf

from single_task import code_tasks  # brain coder
from single_task import defaults  # brain coder


def pad(string, pad_length, pad_char):
  return string + pad_char * (pad_length - len(string))


class CodeTasksTest(tf.test.TestCase):

  def assertClose(self, a, b):
    self.assertTrue(
        np.isclose(a, b, atol=1e-4),
        'Expecting approximately equal values. Got: %s, %s' % (a, b))

  def testMultiIOTaskManager(self):
    maxlen = 100
    padchr = '['
    task = code_tasks.make_paper_task(
        'print', timestep_limit=maxlen, do_code_simplification=False)
    reward_fns = task.rl_batch(1)
    r = reward_fns[0]
    self.assertClose(
        r(pad('++++++++.---.+++++++...', maxlen, padchr)).episode_rewards[-1],
        0.2444)
    self.assertClose(
        r(pad('++++++++.---.+++++++..+++.',
              maxlen, padchr)).episode_rewards[-1],
        1.0)

    task = code_tasks.make_paper_task(
        'print', timestep_limit=maxlen, do_code_simplification=True)
    reward_fns = task.rl_batch(1)
    r = reward_fns[0]
    self.assertClose(
        r('++++++++.---.+++++++...').episode_rewards[-1],
        0.2444)
    self.assertClose(
        r('++++++++.---.+++++++..+++.').episode_rewards[-1],
        0.935)
    self.assertClose(
        r(pad('++++++++.---.+++++++..+++.',
              maxlen, padchr)).episode_rewards[-1],
        0.75)

    task = code_tasks.make_paper_task(
        'reverse', timestep_limit=maxlen, do_code_simplification=False)
    reward_fns = task.rl_batch(1)
    r = reward_fns[0]
    self.assertClose(
        r(pad('>,>,>,.<.<.<.', maxlen, padchr)).episode_rewards[-1],
        0.1345)
    self.assertClose(
        r(pad(',[>,]+[,<.]', maxlen, padchr)).episode_rewards[-1],
        1.0)

    task = code_tasks.make_paper_task(
        'reverse', timestep_limit=maxlen, do_code_simplification=True)
    reward_fns = task.rl_batch(1)
    r = reward_fns[0]
    self.assertClose(r('>,>,>,.<.<.<.').episode_rewards[-1], 0.1324)
    self.assertClose(r(',[>,]+[,<.]').episode_rewards[-1], 0.9725)
    self.assertClose(
        r(pad(',[>,]+[,<.]', maxlen, padchr)).episode_rewards[-1],
        0.75)

  def testMakeTask(self):
    maxlen = 100
    padchr = '['
    config = defaults.default_config_with_updates(
        'env=c(config_for_iclr=False,fixed_string=[8,5,12,12,15])')
    task = code_tasks.make_task(config.env, 'print', timestep_limit=maxlen)
    reward_fns = task.rl_batch(1)
    r = reward_fns[0]
    self.assertClose(
        r('++++++++.---.+++++++...').episode_rewards[-1],
        0.2444)
    self.assertClose(
        r('++++++++.---.+++++++..+++.').episode_rewards[-1],
        0.935)
    self.assertClose(
        r(pad('++++++++.---.+++++++..+++.',
              maxlen, padchr)).episode_rewards[-1],
        0.75)

  def testKnownCodeBaseTask(self):
    maxlen = 100
    padchr = '['
    task = code_tasks.make_paper_task(
        'shift-left', timestep_limit=maxlen, do_code_simplification=False)
    reward_fns = task.rl_batch(1)
    r = reward_fns[0]
    self.assertClose(
        r(pad(',>,[.,]<.,.', maxlen, padchr)).episode_rewards[-1],
        1.0)


if __name__ == '__main__':
  tf.test.main()

#This file: data.py
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

"""Manage data for pretraining and RL tasks."""

import ast
from collections import namedtuple

from absl import logging

from single_task import code_tasks  # brain coder


RLBatch = namedtuple('RLBatch', ['reward_fns', 'batch_size', 'good_reward'])


class DataManager(object):
  """Interface between environment and model."""

  def __init__(self, global_config, run_number=None,
               do_code_simplification=False):
    """Constructs a DataManager.

    Args:
      global_config: A config_lib.Config instance containing all config. See
          config in defaults.py.
      run_number: Which run this is (of the same experiment). This should be set
          when a task cycle is defined in the config. A task cycle is a list of
          tasks to cycle through repeatedly, and the selected task is a function
          of the run number, i.e. 0-th run, 1-st run, 2-nd run, etc...
          This can be None if only a single task is set in the config.
      do_code_simplification: When global_config.env.config_for_iclr is True,
          use this option to create code simplification (code golf) tasks, vs
          fixed length coding tasks. If True, a task with code simplification
          reward will be constructed.

    Raises:
      ValueError: If global_config.env.task and global_config.env.task_cycle
          are both set, or both not set. Only one should be given.
      ValueError: If global_config.env.task_cycle is set but run_number is None.
    """
    env_config = global_config.env
    self.batch_size = global_config.batch_size

    if env_config.task_cycle:
      if env_config.task:
        raise ValueError('Do not set both `task` and `task_cycle`.')
      if run_number is None:
        raise ValueError('Do not use task_cycle for single-run experiment.')
      index = run_number % len(env_config.task_cycle)
      self.task_name = env_config.task_cycle[index]
      logging.info('run_number: %d,  task_cycle index: %d', run_number, index)
      logging.info('task_cycle: %s', env_config.task_cycle)
    elif env_config.task:
      self.task_name = env_config.task
    else:
      raise ValueError('Either `task` or `task_cycle` must be set.')
    logging.info('Task for this run: "%s"', self.task_name)

    logging.info('config_for_iclr=True; do_code_simplification=%s',
                 do_code_simplification)
    self.rl_task = code_tasks.make_task(
        task_name=self.task_name,
        override_kwargs=ast.literal_eval(env_config.task_kwargs),
        max_code_length=global_config.timestep_limit,
        require_correct_syntax=env_config.correct_syntax,
        do_code_simplification=do_code_simplification,
        correct_bonus=env_config.task_manager_config.correct_bonus,
        code_length_bonus=env_config.task_manager_config.code_length_bonus)

  def sample_rl_batch(self):
    """Create reward functions from the current task.

    Returns:
      RLBatch namedtuple instance, which holds functions and information for
      a minibatch of episodes.
      * reward_fns: A reward function for each episode. Maps code string to
          reward.
      * batch_size: Number of episodes in this minibatch.
      * good_reward: Estimated threshold of rewards which indicate the algorithm
          is starting to solve the task. This is a heuristic that tries to
          reduce the amount of stuff written to disk.
    """
    reward_fns = self.rl_task.rl_batch(self.batch_size)
    return RLBatch(
        reward_fns=reward_fns,
        batch_size=self.batch_size,
        good_reward=self.rl_task.good_reward)

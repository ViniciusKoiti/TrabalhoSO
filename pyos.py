import os
import curses
import pycfg
from pyarch import load_binary_into_memory
from pyarch import cpu_t

PYOS_TASK_STATE_READY                       = 0
PYOS_TASK_STATE_EXECUTING                   = 1

class task_t:
	def __init__ (self):
		self.regs = [0, 0, 0, 0, 0, 0, 0, 0]
		self.reg_pc = 0
		self.stack = 0
		self.paddr_offset = 0
		self.paddr_max = 0
		self.bin_name = ""
		self.bin_size = 0
		self.tid = 0
		self.state = PYOS_TASK_STATE_READY

class os_t:
	def __init__ (self, cpu, memory, terminal):
		self.cpu = cpu
		self.memory = memory
		self.terminal = terminal

		self.terminal.enable_curses()

		self.console_str = ""

		self.tasks = []
		
		self.page = 0
		self.next_task_id = 0
		self.current_task = None
		self.next_sched_task = 0
		self.idle_task = None
		self.idle_task = self.load_task("idle.bin")
		
		self.memory_page_size = 4096
		self.blocksize = 256
		self.number_blocks = self.memory.get_size() / self.memory_page_size
		self.memory_blocks = [0] * self.number_blocks

		if self.idle_task is None:
			self.panic("could not load idle.bin task")
		
		self.sched(self.idle_task)

		self.terminal.console_print("this is the console, type the commands here\n")

	def load_task (self, bin_name):
		if not os.path.isfile(bin_name):
			self.printk("file "+bin_name+" does not exists")
			return None
		if (os.path.getsize(bin_name) % 2) == 1:
			self.printk("file size of "+bin_name+" must be even")
			return None
		
		task = task_t()
		task.bin_name = bin_name
		task.bin_size = os.path.getsize(bin_name) / 2 # 2 bytes = 1 word

		task.paddr_offset, task.paddr_max = self.allocate_contiguos_physical_memory_to_task(task.bin_size, task)

		if task.paddr_offset == -1:
			return None

		task.regs = [0, 0, 0, 0, 0, 0, 0, 0]
		task.reg_pc = 1
		task.stack = 0
		task.state = PYOS_TASK_STATE_READY

		self.printk("allocated physical addresses "+str(task.paddr_offset)+" to "+str(task.paddr_max)+" for task "+task.bin_name+" ("+str(self.get_task_amount_of_memory(task))+" words) (binary has "+str(task.bin_size)+" words)")

		self.read_binary_to_memory(task.paddr_offset, task.paddr_max, bin_name)

		self.printk("task "+bin_name+" successfully loaded")

		task.tid = self.next_task_id
		self.next_task_id = self.next_task_id + 1

		#self.tasks.append( task )
		return task

	def read_binary_to_memory (self, paddr_offset, paddr_max, bin_name):
		bpos = 0
		paddr = paddr_offset
		bin_size = os.path.getsize(bin_name) / 2
		i = 0
		with open(bin_name, "rb") as f:
			while True:
				byte = f.read(1)
				if not byte:
					break
				byte = ord(byte)
				if bpos == 0:
					lower_byte = byte
				else:
					word = lower_byte | (byte << 8)
					if paddr > paddr_max:
						self.panic("something really bad happenned when loading "+bin_name+" (paddr > task.paddr_max)")
					self.memory.write(paddr, word)
					paddr = paddr + 1
					i = i + 1
				bpos = bpos ^ 1

		if i != bin_size:
			self.panic("something really bad happenned when loading "+bin_name+" (i != task.bin_size)")

	def sched (self, task):
		if self.current_task is not None:
			self.panic("current_task must be None when scheduling a new one (current_task="+self.current_task.bin_name+")")
		if task.state != PYOS_TASK_STATE_READY:
			self.panic("task "+task.bin_name+" must be in READY state for being scheduled (state = "+str(task.state)+")")

		for i in range(0, 7):
			self.cpu.set_reg(i, task.regs[i])

		self.cpu.set_pc(task.reg_pc)
		task.state = PYOS_TASK_STATE_EXECUTING
		self.cpu.set_paddr_offset(task.paddr_offset)
		self.cpu.set_paddr_max(task.paddr_max)
  
		self.current_task = task
		self.printk("scheduling task "+task.bin_name)

	def get_task_amount_of_memory (self, task):
		return task.paddr_max - task.paddr_offset + 1

	# allocate contiguos physical addresses that have $words
	# returns the addresses of the first and last words to be used by the process
	# -1, -1 if cannot find

	def allocate_contiguos_physical_memory_to_task(self, words, task):
    # TODO Arrumar vazamento de memoria
		if words > self.blocksize:
			return -1,-1
		
		free_block_index = self.memory_blocks.index[0]

		if free_block == -1:
			return -1, -1

		paddr_offset = free_block_index * (self.blocksize - 1)
		paddr_max = free_block_index * self.blocksize - 1
		
		self.memory_blocks[free_block_index] = 1
		return paddr_offset, paddr_max
		

	def printk(self, msg):
		self.terminal.kernel_print("kernel: " + msg + "\n")

	def panic (self, msg):
		self.terminal.end()
		self.terminal.dprint("kernel panic: " + msg)
		self.cpu.cpu_alive = False
		#cpu.cpu_alive = False

	def interrupt_keyboard (self):
		key = self.terminal.get_key_buffer()

		if ((key >= ord('a')) and (key <= ord('z'))) or ((key >= ord('A')) and (key <= ord('Z'))) or ((key >= ord('0')) and (key <= ord('9'))) or (key == ord(' ')) or (key == ord('-')) or (key == ord('_')) or (key == ord('.')):
			self.console_str = self.console_str + chr(key)
			self.terminal.console_print("\r" + self.console_str)
		elif key == curses.KEY_BACKSPACE:
			self.console_str = self.console_str[:-1]
			self.terminal.console_print("\r" + self.console_str)
		elif (key == curses.KEY_ENTER) or (key == ord('\n')):
			self.interpret_cmd(self.console_str)
			self.console_str = ""

	def interpret_cmd (self, cmd):
		if cmd == "bye":
			self.cpu.cpu_alive = False
		elif cmd == "tasks":
			self.task_table_print()
		elif cmd[:3] == "run":
			bin_name = cmd[4:]
			self.terminal.console_print("\rrun binary " + bin_name + "\n")
			task = self.load_task(bin_name)
			if task is not None:
				self.tasks.append(task)
				self.un_sched(self.current_task)
				self.sched(task)
			else:
				self.terminal.console_print("error: binary " + bin_name + " not found\n")
		else:
			self.terminal.console_print("\rinvalid cmd " + cmd + "\n")

	def terminate_unsched_task (self, task):
		if task.state == PYOS_TASK_STATE_EXECUTING:
			self.panic("impossible to terminate a task that is currently running")
		if task == self.idle_task:
			self.panic("impossible to terminate idle task")
		if task is not self.the_task:
			self.panic("task being terminated should be the_task")
		
		#TODO limpar memoria
		self.tasks.remove(task)
		self.printk("task "+task.bin_name+" terminated")

	def un_sched (self, task):
		if task.state != PYOS_TASK_STATE_EXECUTING:
			self.panic("task "+task.bin_name+" must be in EXECUTING state for being unscheduled (state = "+str(task.state)+")")
		if task is not self.current_task:
			self.panic("task "+task.bin_name+" must be the current_task for being unscheduled (current_task = "+self.current_task.bin_name+")")

		# Salvar na task struct
		for i in range(0, 7):
			task.regs[i] = self.cpu.get_reg(i)
		# - registradores de proposito geral
		# - PC
		task.reg_pc = self.cpu.reg_pc
		# Atualizar o estado do processo
		task.state = PYOS_TASK_STATE_READY

		self.current_task = None
  
		self.printk("unscheduling task "+ task.bin_name)

	def virtual_to_physical_addr (self, task, vaddr):
		return task.paddr_offset + vaddr

	def check_valid_vaddr (self, task, vaddr):
		paddr = self.virtual_to_physical_addr(self.current_task, vaddr)
		if paddr > task.paddr_max:
			return False
		else:
			return True

	def handle_gpf (self, error):
		task = self.current_task
		self.printk("gpf task "+task.bin_name+": "+error)
		self.un_sched(task)
		self.terminate_unsched_task(task)
		self.escalonador()

	def interrupt_timer (self):
		# Chamar escalonador
		self.escalonador()

	def handle_interrupt (self, interrupt):
		if interrupt == pycfg.INTERRUPT_MEMORY_PROTECTION_FAULT:
			self.handle_gpf("invalid memory address")
		elif interrupt == pycfg.INTERRUPT_KEYBOARD:
			self.interrupt_keyboard()
		elif interrupt == pycfg.INTERRUPT_TIMER:
			self.interrupt_timer()
		else:
			self.panic("invalid interrupt "+str(interrupt))
	
	def syscall(self):
		service = self.cpu.get_reg(0)
		task = self.current_task

		if service == 0:
			self.printk("app " + self.current_task.bin_name + " solicita finalizacao")
			self.un_sched(self.tasks)
			self.terminate_unsched_task(task)
			self.escalonador()
			
		elif service == 1:
			self.print_string_service(task, self.cpu.get_reg(1))

		elif service == 2:
			self.terminal.app_print("\n")

		elif service == 3:
			self.terminal.app_print(str(self.cpu.get_reg(1)))
		
		else:
			self.handle_gpf("invalid syscall "+str(service))
   
	def escalonador(self):
		if (len(self.tasks) == 0):
			if(self.current_task is None):
				self.sched(self.idle_task)
		if(len(self.tasks) == 1):
			if(self.current_task != self.tasks[0]):
				self.un_sched(self.current_task)
				self.sched(self.tasks[0])
			return
		if(len(self.tasks) > 1):
			task_to_sched = 0
			if(len(self.tasks) - 1 < self.next_sched_task):
				task_to_sched = 0
			else:
				task_to_sched = self.next_sched_task
			self.sched(self.tasks[task_to_sched])
			self.next_sched_task = task_to_sched
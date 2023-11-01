PAGE_SIZE_BITS = 6
PAGE_SIZE = (1 << PAGE_SIZE_BITS)
MEMORY_SIZE_WITH_OS = (16*1024)
MEMORY_SIZE_WITHOUT_OS = 256
NREGS = 8

INTERRUPT_MEMORY_PROTECTION_FAULT       = 1
INTERRUPT_KEYBOARD                      = 2
INTERRUPT_TIMER                         = 3

TIMER_THRESHOLD = 200
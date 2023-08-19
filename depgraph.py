import io
import os
import sys
import typing

SHN_UNDEF = 0
STB_LOCAL = 0
STB_GLOBAL = 1
STB_WEAK = 2
STV_DEFAULT = 0
STV_INTERNAL = 1
STV_HIDDEN = 2
STV_PROTECTED = 3
SIZEOF_SYM = 24

Graph: typing.TypeAlias = dict[str, set[str]]
Symtab: typing.TypeAlias = dict[str, set[str]]
GlobalSyms: typing.TypeAlias = dict[str, str]
WeakSyms: typing.TypeAlias = dict[str, str]
UndefSyms: typing.TypeAlias = dict[str, set[str]]


def read_int(f: typing.BinaryIO, n: int) -> int:
    return int.from_bytes(f.read(n), sys.byteorder)


def read_name(f: typing.BinaryIO, strtab: bytearray) -> str:
    name_off = read_int(f, 4)
    name_end = strtab.find(0, name_off)
    return strtab[name_off:name_end].decode()


def read_section(f: typing.BinaryIO, off: int) -> bytearray:
    f.seek(off + 24)
    sec_off = read_int(f, 8)
    sec_sz = read_int(f, 8)
    f.seek(sec_off)
    return f.read(sec_sz)


def read_syms(objpath: str) -> Symtab:
    out: Symtab = {
        'GLOBAL': set(),
        'WEAK': set(),
        'UNDEF': set(),
    }
    strtab = b''
    symtab = b''
    with open(objpath, 'rb') as f:
        f.seek(40)
        shoff = read_int(f, 8)
        f.seek(58)
        shentsize = read_int(f, 2)
        shnum = read_int(f, 2)
        shstrndx = read_int(f, 2)

        shstrtab = read_section(f, shoff + shstrndx * shentsize)

        for sh in range(shnum):
            f.seek(shoff + sh * shentsize)
            name = read_name(f, shstrtab)
            if name == '.strtab':
                strtab = read_section(f, shoff + sh * shentsize)
            elif name == '.symtab':
                symtab = read_section(f, shoff + sh * shentsize)
    num_syms = len(symtab) // SIZEOF_SYM
    for ns in range(1, num_syms):
        sym = io.BytesIO(symtab[ns * SIZEOF_SYM : (ns + 1) * SIZEOF_SYM])
        st_name = read_name(sym, strtab)
        st_info = read_int(sym, 1)
        st_bind = st_info >> 4
        st_type = st_info & 0xf
        st_vis = read_int(sym, 1)
        st_shndx = read_int(sym, 2)
        if st_shndx != SHN_UNDEF:
            if st_bind == STB_GLOBAL:
                out['GLOBAL'].add(st_name)
            elif st_bind == STB_WEAK:
                out['WEAK'].add(st_name)
        else:
            out['UNDEF'].add(st_name)
    return out


def read_syms_archive(archive_dir: str) -> tuple[GlobalSyms, UndefSyms, WeakSyms]:
    out_globl: GlobalSyms = {}
    out_undef: UndefSyms = {}
    out_weak: WeakSyms = {}
    dups: set[str] = set()

    for f in os.listdir(archive_dir):
        syms = read_syms(os.path.join(archive_dir, f))
        for sym in syms['GLOBAL']:
            if sym in out_globl:
                print(f'{f}: multiple definition of symbol {sym}', file=sys.stderr)
            else:
                out_globl[sym] = f
        for sym in syms['WEAK']:
            if sym not in out_weak:
                out_weak[sym] = f
            else:
                dups.add(sym)
        out_undef[f] = syms['UNDEF']

    for sym in dups:
        del out_weak[sym]

    return out_globl, out_undef, out_weak


def make_graph(archive_dir: str, gsyms: GlobalSyms, usyms: UndefSyms, wsyms: WeakSyms) -> Graph:
    out: Graph = {}
    und: dict[str, set[str]] = {}
    for f in os.listdir(archive_dir):
        deps: set[str] = set()
        for sym in usyms[f]:
            if sym in gsyms:
                deps.add(gsyms[sym])
            elif sym in wsyms:
                deps.add(wsyms[sym])
            else:
                if sym not in und:
                    und[sym] = set()
                und[sym].add(f)
        out[f] = deps

    def print_und(sym: str, fs: set[str]) -> None:
        ns = len(fs)
        print(f'{ns:4} {sym:30}', end='')
        if ns <= 2:
            for f in fs:
                print(f' {f:30}', end='')
        print('')

    for sym in und:
        # print_und(sym, und[sym])
        pass

    return out


def _bfs(graph: Graph, cur_node: str, dot: typing.TextIO) -> None:
    suffix = '.o' if cur_node.endswith('.o') else '.lo'
    nodeq = [cur_node]
    visited: set[str] = set()
    while nodeq:
        cur_node = nodeq.pop()
        visited.add(cur_node)
        p = cur_node.removesuffix(suffix)
        for node in graph[cur_node]:
            if node not in visited:
                q = node.removesuffix(suffix)
                dot.write(f'  "{p}" -> "{q}"\n')
                nodeq.append(node)


def bfs(graph: Graph, start: str) -> None:
    with open('deps.dot', 'w') as dot:
        dot.write('digraph {\n  graph[splines=ortho]\n')
        _bfs(graph, start, dot)
        dot.write('}\n')


def main():
    if len(sys.argv) != 2:
        print(f'Usage: {sys.argv[0]} archive_dir', file=sys.stderr)
        sys.exit(1)
    archive_dir = sys.argv[1]
    gsyms, usyms, wsyms = read_syms_archive(archive_dir)
    graph = make_graph(archive_dir, gsyms, usyms, wsyms)
    bfs(graph, gsyms['__libc_start_main'])


if __name__ == '__main__':
    main()

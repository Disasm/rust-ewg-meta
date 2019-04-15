#!/usr/bin/env python3

import sys
import re


def extract_blocks(lines):
    current_block = []
    blocks = []
    for line in lines + [""]:
        if len(line.strip()) == 0:
            if len(current_block) > 0:
                blocks.append(current_block)
            current_block = []
        else:
            current_block.append(line)
    return blocks


BLOCK_STRUCT = 'struct'
BLOCK_ENUM = 'enum'


def get_block_type(block):
    for line in block:
        if line.startswith("typedef struct "):
            return BLOCK_STRUCT
        if line.startswith("typedef enum "):
            return BLOCK_ENUM


def parse_comment_brief(block):
    for line in block:
        if line.startswith(" */"):
            break
        if line.startswith(" * @brief"):
            return line[9:].strip()


def parse_names(block):
    secondary = None
    primary = None
    for line in block:
        sline = line.strip()
        if line.startswith("typedef"):
            a = sline.split()
            if len(a) == 3:
                secondary = a[2]
        if line.startswith("} ") and sline[-1] == ";":
            primary = sline.split()[-1][:-1]
    return primary, secondary


def extract_contents(block):
    contents = []
    active = False
    for line in block:
        sline = line.strip()
        if line.startswith("{"):
            active = True
            continue
        if active:
            if line.startswith("}"):
                break
            contents.append(sline)
    return contents


def parse_enum(item, block):
    brief = parse_comment_brief(block)
    item['doc'] = brief
    primary, secondary = parse_names(block)
    if primary is None:
        raise Exception("Inexpected enum without primary name")
    else:
        item['name'] = primary

    last_value = -1
    values = dict()
    for sline in extract_contents(block):
        if sline.endswith(","):
            sline = sline[:-1]
        if sline.startswith("/*") or sline.startswith("//"):
            continue

        if '=' in sline:
            s = sline.split("=")[-1].strip()
            value = int(s)
        else:
            value = last_value + 1
        name = sline.split()[0]
        values[name] = value
        last_value = value
    item['values'] = values


def fix_name(field, struct):
    m = re.search(r'sysctl_pll(\d)_t', struct)
    if m:
        i = m.group(1)
        if field.endswith(i):
            field = field[:-1]
        if field.startswith('pll_'):
            field = field[4:]
        return field
    if struct == 'sysctl_general_pll_t':
        if field.startswith('pll_'):
            return field[4:]
    if re.search(r'sysctl_clk_th\d_t', struct):
        if field.endswith('_threshold'):
            return field[:-10]
    return field


def fix_doc(doc, struct):
    if struct == 'sysctl_t':
        m = re.search(r'No. \d+ \(\w+\): (.*)', doc)
        if m:
            return m.group(1)
    return doc


def parse_struct(item, block):
    brief = parse_comment_brief(block)
    item['doc'] = brief
    primary, secondary = parse_names(block)
    if primary is None:
        raise Exception("Inexpected struct without primary name")
    else:
        item['name'] = primary

    contains_bitfields = False
    for line in extract_contents(block):
        m = re.search(r'\w+ : \d+;', line)
        if m:
            contains_bitfields = True
    item['main'] = not contains_bitfields

    if contains_bitfields:
        fields = []
        offset = 0
        for line in extract_contents(block):
            if line.startswith("/*!< ") and line.endswith("*/"):
                doc = line[4:-2].strip()
                if doc.endswith('.'):
                    doc = doc[:-1]
                if 'doc' not in fields[-1]:
                    fields[-1]['doc'] = doc
                continue

            m = re.search(r'(\w+) (\w+)\s*: (\d+);', line)
            if m:
                t = m.group(1)
                if t != "uint32_t":
                    raise Exception("Unexpected type in '%s'" % line)
                name = fix_name(m.group(2), item['name'])
                width = int(m.group(3))
                field = {
                    'type': t,
                    'name': name,
                    'offset': offset,
                    'width': width,
                }
                is_reserved = name.startswith('reserved') or re.search(r'resv\d+', name)
                if not is_reserved:
                    fields.append(field)
                offset += width
                continue
            raise Exception("Invalid item: '%s'" % line)
        item['fields'] = fields
    else:
        item['registers'] = []
        doc = None
        for line in extract_contents(block):
            if line.startswith('/*'):
                doc = line[2:-2].strip()
                doc = fix_doc(doc, item['name'])
            else:
                m = re.search(r'(\w+) (\w+);', line)
                if m:
                    t = m.group(1)
                    name = m.group(2)
                    reg = {
                        'type': t,
                        'name': name,
                        'doc': doc,
                    }
                    item['registers'].append(reg)
                else:
                    if item['name'] in ['fpioa_tie_t', 'fpioa_t']:
                        return
                    raise Exception("Invalid item: '%s'" % line)
                doc = None


def parse_header(filename):
    f = open(filename, "rt")
    lines = f.read().split("\n")
    blocks = extract_blocks(lines)
    items = []
    for block in blocks:
        t = get_block_type(block)
        if t is None:
            continue
        item = dict()
        item['type'] = t
        #if t == BLOCK_ENUM:
        #    parse_enum(item, block)
        if t == BLOCK_STRUCT:
            parse_struct(item, block)
        items.append(item)
    return items


def print_enum(item):
    if 'doc' in item:
        print("<!-- %s -->" % item['doc'])
    print("<enumeratedValues>")
    print("  <name>%s</name>" % item['name'])
    for (name, value) in item['values'].items():
        print("  <enumeratedValue>")
        print("    <name>%s</name>" % name)
        print("    <value>%d</value>" % value)
        print("  </enumeratedValue>")
    print("</enumeratedValues>")


def find_struct(items, type_name):
    for item in items:
        if item['type'] == BLOCK_STRUCT and item['name'] == type_name:
            return item


def find_main_struct(items):
    for item in items:
        if item['type'] == BLOCK_STRUCT and item['main']:
            return item


def print_fields_struct(item):
    print("<fields>")
    for field in item['fields']:
        print("  <field>")
        print("    <name>%s</name>" % field['name'])
        if 'doc' in field:
            print("    <description>%s</description>" % field['doc'])
        lsb = field['offset']
        msb = lsb + field['width'] - 1
        print("    <bitRange>[%d:%d]</bitRange>" % (msb, lsb))
        print("  </field>")
    print("</fields>")


def print_main_struct(item, items):
    if item['doc'] is not None:
        print("<!-- %s -->" % item['doc'])
    print("<!-- %s -->" % item['name'])
    print("<registers>")
    address = 0
    for reg in item['registers']:
        is_reserved = reg['type'] == 'uint32_t' and reg['name'].startswith('resv')
        if not is_reserved:
            print("  <register>")
            print("    <name>%s</name>" % reg['name'])
            print("    <description>%s</description>" % reg.get('doc', ''))
            print("    <addressOffset>0x%02x</addressOffset>" % address)
            s = find_struct(items, reg['type'])
            print_fields_struct(s)
            print("  </register>")
        address += 4
    print("</registers>")


def main():
    if len(sys.argv) < 2:
        print("Usage: %s /path/to/kendryte-standalone-sdk/lib/drivers/include/<driver>.h > output.xml")
        return
    filename = sys.argv[1]
    items = parse_header(filename)

    print("<root>")
    for item in items:
        if item['type'] == BLOCK_ENUM + 'a':
            print()
            print_enum(item)
        #if item['type'] == BLOCK_STRUCT:
            #print()
            #if not item['main']:
            #    print_fields_struct(item)
    #print_main_struct(find_main_struct(items), items)
    print_fields_struct(find_struct(items, 'fpioa_io_config_t'))
    print("</root>")


if __name__ == "__main__":
    main()

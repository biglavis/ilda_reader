def read_ilda(file: str):
    """
    Reads ILDA file as binary.

    Returns:
        string: data that was read.
    """

    if file.endswith(".ild"):
        with open(rf'{file}', 'rb') as f:
            return f.read()
        
def unpack_ilda(file: str, filter = True):
    """
    Reads ILDA file.
    
    Returns:
        generator: a generator object that yields frame information.
    """
    
    if data := read_ilda(file):
        return unpack_data(data, filter)
        
def unpack_data(data, filter: bool):
    """
    Reads ILDA data.

    Yields:
        tuple: frame <int>, num_frams <int>, records <list>.
    """

    next_data = data
    while True:
        header, next_data = read_header(next_data)

        # restart if EOF
        if header['num_records'] == 0:
            header, next_data = read_header(data)

        records, next_data = read_records(next_data, **header)

        if records:
            if filter: 
                yield header['frame'], header['num_frames'], filter_records(records)
            else:
                yield header['frame'], header['num_frames'], records

def read_header(data):
    """
    Reads header from ILDA data.

    Returns:
        dict: header.
        string: remaining data.
    """

    header = {
        "format": data[7],
        "num_records": int.from_bytes(data[24:26], byteorder='big', signed=False),
        "frame": int.from_bytes(data[26:28], byteorder='big', signed=False),
        "num_frames": int.from_bytes(data[28:30], byteorder='big', signed=False)
    }

    return header, data[32:]

def read_records(data, format, num_records, **kwargs):
    """
    Reads records from ILDA data.

    Returns:
        list: records.
        string: remaining data.
    """

    record_size = {
        "0": 8,
        "1": 6,
        "2": 3,
        "4": 10,
        "5": 8
    }

    size = record_size[f'{format}']

    if format == 2:
        return None, data[num_records*size:]
    
    records = [data[i*size:(i+1)*size] for i in range(num_records)]
    records = [read_record(record, format) for record in records]

    return records, data[num_records*size:]

def read_record(record, format):
    """
    Reads ILDA record.

    Returns:
        tuple: x-coordinate <int>, y-coordinate <int>, status <bool>.
    """

    x = int.from_bytes(record[0:2], byteorder='big', signed=True)
    y = int.from_bytes(record[2:4], byteorder='big', signed=True)
    
    if format in [0,1]:
        status = False if (record[-2] & (1 << 6)) else True
    else:
        status = False if (record[-4] & (1 << 6)) else True

    return x, y, status

def filter_records(records: list, tol: float = 0.002):
    """
    Removes duplicates, superfluous "off" records, and straight lines using linear regression.

    Returns:
        list: filtered records.
    """

    # remove duplicates and superfluous records
    records = [pos for i,pos in enumerate(records) if i+1 == len(records) or (pos != records[i+1] and (pos[2] or records[i+1][2]))]

    # remove straight lines
    filtered = []
    for i in range(len(records)):
        if i == 0 or i+1 == len(records):
            filtered.append(records[i])
            continue

        x0, y0, s0 = records[i-1]
        x1, y1, s1 = records[i]
        x2, y2, s2 = records[i+1]

        if s0 != s1 or s1 != s2:
            filtered.append(records[i])
            continue   

        if x0 == x1:
            if x1 != x2:
                filtered.append(records[i])
            continue

        m = (y1-y0)/(x1-x0)
        b = y0 - m*x0
        y2s = m*x2 + b

        if y2s < y2 - 65535*tol or y2s > y2 + 65535*tol:
            filtered.append(records[i])

    return filtered

def read_ilda(file: str):
    if file.endswith(".ild"):
        with open(rf'{file}', 'rb') as f:
            return f.read()
        
def unpack_ilda(file: str, filter = True):
    if data := read_ilda(file):
        return unpack_data(data, filter)
        
def unpack_data(data, filter: bool):
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
    header = {
        "format": data[7],
        "num_records": int.from_bytes(data[24:26], byteorder='big', signed=False),
        "frame": int.from_bytes(data[26:28], byteorder='big', signed=False),
        "num_frames": int.from_bytes(data[28:30], byteorder='big', signed=False)
    }

    return header, data[32:]

def read_records(data, format, num_records, **kwargs):
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
    positions = [read_record(record, format) for record in records]

    return positions, data[num_records*size:]

def read_record(record, format):
    x = int.from_bytes(record[0:2], byteorder='big', signed=True)
    y = int.from_bytes(record[2:4], byteorder='big', signed=True)
    
    if format in [0,1]:
        status = False if (record[-2] & (1 << 6)) else True
    else:
        status = False if (record[-4] & (1 << 6)) else True

    return x, y, status

def filter_records(records: list):
    return [pos for i,pos in enumerate(records) if pos[2] or i+1 == len(records) or records[i+1][2]]
        
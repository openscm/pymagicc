classdef EmisFileWriter < object_oriented_simcap.Writers.MAGICCDataFileWriter
    methods (Access=protected)
        function Data_value = return_Data_descriptor(self)
            return_Data_descriptor@object_oriented_simcap.Writers.MAGICCDataFileWriter(self);
            % can make this much nicer with I, B descriptions once we sort
            % out MAGICC's variable descriptor rules
            Data_value = [...
                'Average emissions per year'...
            ];
        end
        
        function renamed_cell_datablock = return_renamed_cell_datablock(self,cell_datablock)
            renamed_cell_datablock = cell_datablock;
            variable_idx = strcmpi(renamed_cell_datablock,'Variable');
            renamed_cell_datablock{variable_idx} = 'GAS';
            unit_idx = strcmpi(renamed_cell_datablock,'Unit');
            renamed_cell_datablock{unit_idx} = 'UNITS';
        end
    end
end
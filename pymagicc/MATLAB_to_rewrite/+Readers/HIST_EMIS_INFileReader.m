classdef HIST_EMIS_INFileReader < object_oriented_simcap.Readers.MAGICCDataFileReader
    methods (Access = protected)
        function make_Region_header_row_in_header_rows_tmp(self)
            Replace_cell_idx = strcmp(self.header_rows_tmp,'YEARS')...
                               | strcmp(self.header_rows_tmp,'COLCODE');
            self.header_rows_tmp(Replace_cell_idx) = {'Region'};
        end
        function make_Variable_header_row_in_header_rows_tmp(self)
            GAS_cell_idx = strcmp(self.header_rows_tmp,'GAS');
            if any(GAS_cell_idx(:))
                self.header_rows_tmp(GAS_cell_idx) = {'Variable'};
            else
                repeated_variable_cell = repmat(...
                    {self.extract_variable_from_filename},...
                    1,size(self.header_rows_tmp,2) -1 ...
                );
                variable_row = ['Variable' repeated_variable_cell];
                self.header_rows_tmp = [variable_row;self.header_rows_tmp];
            end
        end
        function variable = extract_variable_from_filename(self)
            variable = char(regexp(...
                self.data.full_path_source_file,...
                '(?<=_)\w*(?=_EMIS.IN)','match'...
            ));
        end
        function make_TODO_header_row_in_header_rows_tmp(self)
            repeated_TODO_cell = repmat(...
                {'SET'},...
                1,size(self.header_rows_tmp,2)-1 ...
            );
            TODO_row = ['TODO' repeated_TODO_cell];
            self.header_rows_tmp = [TODO_row;self.header_rows_tmp];
        end
    end
end
classdef SCEN7FileWriter < object_oriented_simcap.Writers.EmisFileWriter
    methods (Access = protected)
        function file_header_formatted = get_file_header(self)
            % doesn't look quite right as you have to escape apostrophes
            file_header = [...
                '.__  __          _____ _____ _____ _____ ______                  _         _                                                 _' self.newline_char...
                '|  \/  |   /\   / ____|_   _/ ____/ ____|____  |                (_)       (_)                                               (_)' self.newline_char...
                '| \  / |  /  \ | |  __  | || |   | |        / /    ___ _ __ ___  _ ___ ___ _  ___  _ __  ___   ___  ___ ___ _ __   __ _ _ __ _  ___' self.newline_char...
                '| |\/| | / /\ \| | |_ | | || |   | |       / /    / _ \ ''_ ` _ \| / __/ __| |/ _ \| ''_ \/ __| / __|/ __/ _ \ ''_ \ / _` | ''__| |/ _ \' self.newline_char...
                '| |  | |/ ____ \ |__| |_| || |___| |____  / /    |  __/ | | | | | \__ \__ \ | (_) | | | \__ \ \__ \ (_|  __/ | | | (_| | |  | | (_) |' self.newline_char...
                '|_|  |_/_/    \_\_____|_____\_____\_____|/_/      \___|_| |_| |_|_|___/___/_|\___/|_| |_|___/ |___/\___\___|_| |_|\__,_|_|  |_|\___/'...
            ];
            file_header_formatted = object_oriented_simcap.Utils.return_sprintf_compatible_string(...
                file_header...
            );
        end
        function number_format_code = get_number_format_code(self)
            number_format_code = '.4f';
        end
        
        function renamed_cell_datablock = return_renamed_cell_datablock(self,cell_datablock)
            renamed_cell_datablock = return_renamed_cell_datablock@object_oriented_simcap.Writers.EmisFileWriter(...
                self,...
                cell_datablock...
            );
            region_idx = strcmpi(renamed_cell_datablock,'Region');
            renamed_cell_datablock{region_idx} = 'YEARS';
        end
        
        function region_reordered_cell_datablock = return_region_reordered_cell_datablock(self,renamed_cell_datablock)
            % order doesn't matter for SCEN7
            region_reordered_cell_datablock = renamed_cell_datablock;
        end
        function header_row_order = get_header_row_order(self)
            header_row_order = {'GAS' 'TODO' 'UNITS' 'YEARS'};
        end
        
        function set_THISFILE_DATTYPE_THISFILE_REGIONMODE_region_column_order(self)
            set_THISFILE_DATTYPE_THISFILE_REGIONMODE_region_column_order@object_oriented_simcap.Writers.MAGICCDataFileWriter(self)
            % will be able to remove this hard coding in future once we
            % work out our conventions better
            self.THISFILE_DATTYPE = 'SCEN7';
        end
    end
end

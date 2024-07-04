import logging

import colorama as co


class MultiLineFormatter(logging.Formatter):
    """A formatter that is aware of multiline log records and provides a facility to indent them.

    Slightly modified version of an SO answer: https://stackoverflow.com/a/66855071. Thanks!
    """

    def __init__(self, *args, indentfunc=None, **kwargs):
        """Construct the formatter.

        You can provide a callable as `indentfunc` that takes one parameter (indentation width) and returns a string
        with which the 2..Nth lines of the log record will be padded.
        """
        self.indentfunc = indentfunc or (lambda width: " " * width)
        super().__init__(*args, **kwargs)

    def get_header_length(self, record):
        """Get the header length of a given record."""
        return len(
            super().format(
                logging.LogRecord(
                    name=record.name,
                    level=record.levelno,
                    pathname=record.pathname,
                    lineno=record.lineno,
                    msg="",
                    args=(),
                    exc_info=None,
                )
            )
        )

    def format(self, record):
        """Format a record with added indentation."""
        indent = self.indentfunc(self.get_header_length(record))
        return super().format(record).replace("\n", f"\n{indent}")


class FriendlyFormatter(MultiLineFormatter, logging.Formatter):
    """Nice and soft formatter that is reasonably terse, colors messages and indents multiline logs when necessary.

    Guaranteed to print INFO from the default logger as-is, except for adding a timestamp when `datefmt` is specified.
    """

    def __init__(self, *args, rootname=None, **kwargs):
        """Construct the formatter.

        Args:
            rootname: The top-level name of your application's logger. If the logger name equals `rootname`, info
                      messages will be printed as-is, and warning/error will be prefixed with "Warning:" and "Error:".
                      If logger name starts with `rootname.` that prefix will be stripped.
        """
        self.rootname = rootname or ""
        super().__init__(*args, **kwargs)

    def format(self, record):
        timestamp = "%(asctime)s "
        if not self.datefmt:
            timestamp = ""

        if record.name == self.rootname:
            self.indentfunc = lambda width: ""  # No indent

            if record.levelno <= logging.INFO:
                self._style._fmt = f"{timestamp}%(message)s"
            else:
                record.levelname = record.levelname.title()

                style = co.Fore.RED
                if record.levelno <= logging.WARNING:
                    style = co.Fore.YELLOW

                self._style._fmt = f"{timestamp}{style}%(levelname)s: %(message)s"
        else:
            self.indentfunc = lambda width: f"{'| ':>{width}}"

            prefix = f"{self.rootname}."
            if record.name.startswith(prefix):
                record.name = record.name[len(prefix) :]

            if record.levelno == logging.INFO:
                self._style._fmt = f"{timestamp}%(name)s | %(message)s"
            else:
                self._style._fmt = f"{timestamp}%(name)s | %(levelname)s | %(message)s"

        return super().format(record)

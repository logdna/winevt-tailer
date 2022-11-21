TAILER_TYPE = "winevt-tailer"

DEFAULT_LOOKBACK = 100  # per channel
DEFAULT_TAILER_NAME = "tail1"

# API version 1, no crc appended to log lines, no ACKs expected on stdin
STARTUP_HELLO = '{"Tailer":{"name":"%s","type":'+ TAILER_TYPE + ',"version":1,"payload":"JSON","crc":false,' \
                '"acks":false}}\n '

DEFAULT_LOG_DIR = 'c:/ProgramData/logs'
DEFAULT_DATA_DIR = 'c:/ProgramData/' + TAILER_TYPE

DEFAULT_TAILER_CONFIG = '''\
channels:
   - name: Application
     query: "*"
   - name: System
     query: "*"
transforms:
    - winevt_tailer.transforms.xml_remove_binary
    - winevt_tailer.transforms.xml_render_message
    - winevt_tailer.transforms.xml_to_json
bookmarks_dir: "''' + DEFAULT_DATA_DIR + '''"    
'''

DEFAULT_LOGGING_SERVICE = '''\
version: 1
disable_existing_loggers: true
formatters:
  simple:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  msg_only:
    format: '%(message)s'
handlers:
  file_tail:  # tail output, message only
    class: winevt_tailer.utils.RotatingFileHandler
    formatter: msg_only
    filename: "''' + DEFAULT_LOG_DIR + '''/windows_{0}.log"    
    level: INFO
    formatter: msg_only
    maxBytes: 10000000 
    backupCount: 1
    encoding: utf8
  file_svc:  # Service log
    class: winevt_tailer.utils.RotatingFileHandler
    formatter: msg_only
    filename: "''' + DEFAULT_LOG_DIR + '''/''' + TAILER_TYPE + '''_{0}.log"    
    level: INFO
    formatter: simple
    maxBytes: 10000000 
    backupCount: 1
    encoding: utf8
loggers:
  tail_out: 
      level: INFO
      handlers: [file_tail]
root: # all log
  level: INFO
  handlers: [file_svc]
'''

DEFAULT_LOGGING_CONSOLE = '''\
version: 1
disable_existing_loggers: true
formatters:
  simple:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  msg_only:
    format: '%(message)s'
handlers:
  stdout: # tail output
    class: logging.StreamHandler
    level: INFO
    formatter: msg_only
    stream: ext://sys.stdout
  stderr: # log
    class: logging.StreamHandler
    level: INFO
    formatter: msg_only
    stream: ext://sys.stderr
loggers:
  tail_out:
      level: INFO
      handlers: [stdout]
root: # all log
  level: WARNING
  handlers: [stderr]
'''

XSLT_XML_TO_JSON = '''\
<?xml version="1.0"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="text" encoding="utf-8"/>
 
    <xsl:template match="/*[node()]">
        <xsl:text>{</xsl:text>
        <xsl:apply-templates select="." mode="detect" />
        <xsl:text>}</xsl:text>
    </xsl:template>
 
    <xsl:template match="*" mode="detect">
        <xsl:choose>
            <xsl:when test="name(preceding-sibling::*[1]) = name(current()) and name(following-sibling::*[1]) != name(current())">
                    <xsl:apply-templates select="." mode="obj-content" />
                <xsl:text>]</xsl:text>
                <xsl:if test="count(following-sibling::*[name() != name(current())]) &gt; 0">, </xsl:if>
            </xsl:when>
            <xsl:when test="name(preceding-sibling::*[1]) = name(current())">
                    <xsl:apply-templates select="." mode="obj-content" />
                    <xsl:if test="name(following-sibling::*) = name(current())">, </xsl:if>
            </xsl:when>
            <xsl:when test="following-sibling::*[1][name() = name(current())]">
                <xsl:text>"</xsl:text><xsl:value-of select="name()"/><xsl:text>" : [</xsl:text>
                    <xsl:apply-templates select="." mode="obj-content" /><xsl:text>, </xsl:text>
            </xsl:when>
            <xsl:when test="count(./child::*) > 0 or count(@*) > 0">
                <xsl:text>"</xsl:text><xsl:value-of select="name()"/>" : <xsl:apply-templates select="." mode="obj-content" />
                <xsl:if test="count(following-sibling::*) &gt; 0">, </xsl:if>
            </xsl:when>
            <xsl:when test="count(./child::*) = 0">
                <xsl:text>"</xsl:text><xsl:value-of select="name()"/>" : "<xsl:apply-templates select="."/><xsl:text>"</xsl:text>
                <xsl:if test="count(following-sibling::*) &gt; 0">, </xsl:if>
            </xsl:when>
        </xsl:choose>
    </xsl:template>
 
    <xsl:template match="*" mode="obj-content">
        <xsl:text>{</xsl:text>
            <xsl:apply-templates select="@*" mode="attr" />
            <xsl:if test="count(@*) &gt; 0 and (count(child::*) &gt; 0 or text())">, </xsl:if>
            <xsl:apply-templates select="./*" mode="detect" />
            <xsl:if test="count(child::*) = 0 and text() and not(@*)">
                <xsl:text>"</xsl:text><xsl:value-of select="name()"/>" : "<xsl:value-of select="text()"/><xsl:text>"</xsl:text>
            </xsl:if>
            <xsl:if test="count(child::*) = 0 and text() and @*">
                <xsl:text>"text" : "</xsl:text><xsl:value-of select="text()"/><xsl:text>"</xsl:text>
            </xsl:if>
        <xsl:text>}</xsl:text>
        <xsl:if test="position() &lt; last()">, </xsl:if>
    </xsl:template>
 
    <xsl:template match="@*" mode="attr">
        <xsl:text>"</xsl:text><xsl:value-of select="name()"/>" : "<xsl:value-of select="."/><xsl:text>"</xsl:text>
        <xsl:if test="position() &lt; last()">,</xsl:if>
    </xsl:template>
 
    <xsl:template match="node/@TEXT | text()" name="removeBreaks">
        <xsl:param name="pText" select="normalize-space(.)"/>
        <xsl:choose>
            <xsl:when test="not(contains($pText, '&#xA;'))"><xsl:copy-of select="$pText"/></xsl:when>
            <xsl:otherwise>
                <xsl:value-of select="concat(substring-before($pText, '&#xD;&#xA;'), ' ')"/>
                <xsl:call-template name="removeBreaks">
                    <xsl:with-param name="pText" select="substring-after($pText, '&#xD;&#xA;')"/>
                </xsl:call-template>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
 
</xsl:stylesheet>
'''

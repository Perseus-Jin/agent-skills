#!/usr/bin/env python3
"""
小说章节拆分工具
自动检测章节格式并按章节拆分长篇小说的txt文件
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple, List, Dict

# 默认章节模式（按优先级排序）
DEFAULT_PATTERNS = [
    r'^第([零一二三四五六七八九十百千]+)[章卷]',      # 中文数字：第一章、第二十三章
    r'^第(\d+)[章卷]',                                 # 阿拉伯数字：第1章、第12章
    r'^Chapter\s+(\d+)',                               # 英文 Chapter 1
    r'^chapter\s+(\d+)',                               # 英文 chapter 1
    r'^第[0-9零一二三四五六七八九十百千]+章.*$',       # 宽松匹配：第1章、第一百二十三章
    r'^\s*\d+\.\s+',                                   # 数字加点：1. 、12.
    r'^\s*\d+\s+',                                     # 数字开头：1 、12
]


def parse_chinese_number(text: str) -> Optional[int]:
    """将中文数字转换为阿拉伯数字"""
    if not text:
        return None
    
    chinese_to_arabic = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '百': 100, '千': 1000
    }
    
    try:
        # 简单处理：对于"十二"这样的组合，拆分成单个字符处理
        result = 0
        temp = 0
        for char in text:
            if char in chinese_to_arabic:
                value = chinese_to_arabic[char]
                if value >= 100:
                    temp *= value
                elif value >= 10:
                    temp = temp * 10 + value if temp else value
                else:
                    temp += value
            elif char == '万':
                result += temp * 10000
                temp = 0
            elif char == '亿':
                result += temp * 100000000
                temp = 0
        
        result += temp
        return result if result > 0 else None
    except:
        return None


def detect_encoding(file_path: str) -> str:
    """检测文件编码"""
    encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'big5', 'shift_jis']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                f.read()
            return encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    return 'utf-8'


def detect_chapter_pattern(content: str) -> Tuple[Optional[re.Pattern], str]:
    """自动检测章节模式"""
    lines = content.split('\n')[:100]  # 只检查前100行
    
    for pattern in DEFAULT_PATTERNS:
        for line in lines:
            if re.match(pattern, line.strip()):
                return re.compile(pattern, re.MULTILINE), pattern
    
    return None, ''


def split_chapters(
    input_file: str,
    output_dir: Optional[str] = None,
    custom_pattern: Optional[str] = None,
    encoding: Optional[str] = None,
    use_chapter_title: bool = True
) -> Dict[str, any]:
    """
    拆分小说章节
    
    Args:
        input_file: 输入的小说文件路径
        output_dir: 输出目录（默认与原文件同级）
        custom_pattern: 自定义章节分隔正则表达式
        encoding: 文件编码（默认自动检测）
        use_chapter_title: 是否使用章节标题作为文件名
    
    Returns:
        包含拆分结果的字典
    """
    
    # 参数验证
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"文件不存在: {input_file}")
    
    # 检测编码
    if encoding is None:
        encoding = detect_encoding(input_file)
    
    # 读取文件
    with open(input_file, 'r', encoding=encoding, errors='replace') as f:
        content = f.read()
    
    # 确定输出目录
    if output_dir is None:
        output_dir = os.path.dirname(input_file)
    output_dir = os.path.join(output_dir, '正文')
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取基础文件名（不含扩展名）
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    
    # 编译正则表达式
    if custom_pattern:
        try:
            chapter_pattern = re.compile(custom_pattern, re.MULTILINE)
            pattern_desc = f"自定义: {custom_pattern}"
        except re.error as e:
            raise ValueError(f"自定义正则表达式无效: {e}")
    else:
        chapter_pattern, pattern_desc = detect_chapter_pattern(content)
        if chapter_pattern is None:
            raise ValueError("无法自动检测章节格式，请使用自定义章节模式")
    
    # 查找所有章节起始位置
    chapter_matches = list(chapter_pattern.finditer(content))
    chapters = []
    
    for i, match in enumerate(chapter_matches):
        start = match.start()
        chapter_title = match.group(0).strip()
        chapter_num = match.group(1) if match.groups() else str(len(chapters) + 1)
        
        # 获取章节标题（整行）
        line_start = content.rfind('\n', 0, start) + 1 if '\n' in content[:start] else 0
        full_title_line = content[line_start:start].strip()
        if not full_title_line:
            full_title_line = chapter_title
        
        # 章节结束位置：下一章标题的起始位置，否则为文件末尾
        if i + 1 < len(chapter_matches):
            end = chapter_matches[i + 1].start()
        else:
            end = len(content)
        
        # 清理标题用于文件名
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', full_title_line)
        safe_title = safe_title.strip()[:50]
        
        # 如果是第X章格式，确保包含完整编号
        if re.match(r'^第', full_title_line) and not re.match(r'^第\d+', safe_title):
            num = parse_chinese_number(chapter_num)
            if num is not None:
                safe_title = f"第{num}章"
            else:
                safe_title = f"第{chapter_num}章"
        
        chapters.append({
            'start': start,
            'end': end,
            'title': full_title_line,
            'filename': f"第{chapter_num.zfill(4)}章.md",
            'chapter_num': chapter_num
        })
    
    # 添加最后一个章节（从最后一章标题行结束后到文件末尾）
    last_end = len(content)
    
    if last_end < len(content):
        remaining = content[last_end:].strip()
        if remaining:
            chapters.append({
                'start': last_end,
                'end': len(content),
                'title': '后记/尾声',
                'filename': f"第{str(len(chapters) + 1).zfill(4)}章.md",
                'chapter_num': str(len(chapters) + 1)
            })
    
    # 写入章节文件
    created_files = []
    for i, chapter in enumerate(chapters):
        chapter_content = content[chapter['start']:chapter['end']].strip()
        
        # 移除标题头部，仅保留正文
        final_content = chapter_content
        
        output_path = os.path.join(output_dir, chapter['filename'])
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
        created_files.append(output_path)
    
    return {
        'success': True,
        'input_file': input_file,
        'output_dir': output_dir,
        'pattern_used': pattern_desc,
        'encoding': encoding,
        'chapters_found': len(chapters),
        'files_created': created_files
    }


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='将长篇小说按章节拆分成多个文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  %(prog)s novel.txt                           # 自动检测章节格式
  %(prog)s novel.txt -o ./chapters            # 指定输出目录
  %(prog)s novel.txt -p "^第\\d+章"            # 使用自定义正则表达式
  %(prog)s novel.txt --encoding gbk           # 指定文件编码
        '''
    )
    
    parser.add_argument('input', help='输入的小说文件路径')
    parser.add_argument('-o', '--output', help='输出目录（默认与原文件同级）')
    parser.add_argument('-p', '--pattern', help='自定义章节分隔正则表达式')
    parser.add_argument('-e', '--encoding', help='文件编码（默认自动检测）')
    parser.add_argument('--no-title-filename', action='store_true',
                        help='不使用章节标题作为文件名')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示详细信息')
    
    args = parser.parse_args()
    
    try:
        result = split_chapters(
            input_file=args.input,
            output_dir=args.output,
            custom_pattern=args.pattern,
            encoding=args.encoding,
            use_chapter_title=not args.no_title_filename
        )
        
        print(f"[OK] Split complete!")
        print(f"  Input: {result['input_file']}")
        print(f"  Output dir: {result['output_dir']}")
        print(f"  Pattern: {result['pattern_used']}")
        print(f"  Encoding: {result['encoding']}")
        print(f"  Chapters: {result['chapters_found']}")
        print(f"  Files:")
        
        for i, f in enumerate(result['files_created'], 1):
            print(f"    {i}. {os.path.basename(f)}")
        
        if args.verbose:
            print(f"\nFull paths:")
            for f in result['files_created']:
                print(f"  {f}")
                
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
